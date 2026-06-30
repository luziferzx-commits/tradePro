from typing import Optional
from collections import defaultdict, deque
from decimal import Decimal
from dataclasses import replace
from numbers import Number
from gqos.messaging.contracts import MessageEnvelope
from gqos.execution.pipeline import IPipelineStage, StageResult, PipelineContext
from gqos.sizing.events import SizePositionCommand, PositionSizedEvent, SizingFailedEvent
from gqos.sizing.models import SizingRequest
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.policies import ISizingPolicy
from gqos.sizing.portfolio import PortfolioSnapshot
from gqos.risk.events import ExecuteTradeCommand, TradeRejectedByCircuitBreaker, TradeRejectedByExposureLimit, TradeRejectedByRiskEvent, RiskBudgetAllocated
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.portfolio.manager import PortfolioManager
from gqos.portfolio.events import CashReservedEvent, CashReleasedEvent, TradeRejectedByPortfolioEvent
from gqos.messaging.bus import ICommandBus
from gqos.accounting.valuation import ValuationEngine

class PortfolioSnapshotStage(IPipelineStage):
    def __init__(self, manager: PortfolioManager, valuation_engine: Optional[ValuationEngine] = None):
        self._manager = manager
        self._valuation_engine = valuation_engine
        
    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, SizePositionCommand):
            return StageResult.continue_with(envelope)
            
        strategy_id = envelope.payload.strategy_id
        
        unrealized_pnl = Decimal('0')
        if self._valuation_engine:
            try:
                alloc = self._manager.state.allocations.get(strategy_id)
                settled_cash = alloc.allocated_capital if alloc else Decimal('0')
                val = self._valuation_engine.calculate_strategy_nav(strategy_id, settled_cash)
                unrealized_pnl = val.total_unrealized_pnl
            except Exception as e:
                return StageResult.halt(f"Valuation Failed: {str(e)}", events=[])
                
        snapshot = self._manager.generate_snapshot(strategy_id, unrealized_pnl)
        context.snapshot = snapshot
        return StageResult.continue_with(envelope)

class SizingStage(IPipelineStage):
    def __init__(self, engine: PositionSizingEngine, policy: ISizingPolicy):
        self._engine = engine
        self._policy = policy
        
    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, SizePositionCommand):
            return StageResult.continue_with(envelope)
            
        cmd = envelope.payload
        request = SizingRequest(
            strategy_id=cmd.strategy_id,
            symbol=cmd.symbol,
            direction=cmd.direction,
            entry_price=cmd.entry_price,
            stop_loss_price=cmd.stop_loss_price,
            conviction=cmd.conviction,
            metrics=cmd.metrics,
            volatility=cmd.volatility
        )
        
        portfolio = context.snapshot
        if portfolio is None:
            return StageResult.halt("Sizing Failed: No PortfolioSnapshot injected", events=[])
            
        try:
            result = self._engine.size_trade(request, self._policy, portfolio)
        except Exception as e:
            failed_event = SizingFailedEvent(
                strategy_id=cmd.strategy_id,
                symbol=cmd.symbol,
                direction=cmd.direction,
                reason=str(e)
            )
            return StageResult.halt(f"Sizing Failed: {str(e)}", events=[failed_event])
            
        sized_event = PositionSizedEvent(
            strategy_id=cmd.strategy_id,
            symbol=cmd.symbol,
            direction=cmd.direction,
            result=result,
            policy_name=self._policy.policy_name,
            policy_version=self._policy.policy_version,
            policy_parameters_hash=self._policy.policy_parameters_hash,
            dynamic_stop_loss=result.dynamic_stop_loss
        )
        
        execute_cmd = ExecuteTradeCommand(
            symbol=cmd.symbol,
            direction=cmd.direction,
            quantity=result.quantity,
            estimated_value=result.estimated_value,
            strategy_id=cmd.strategy_id,
            decision_id=getattr(cmd, 'decision_id', ''),
            stop_loss=cmd.stop_loss_price,
            take_profit=cmd.take_profit_price
        )
        
        new_env = MessageEnvelope.create(
            execute_cmd,
            version=envelope.version,
            correlation_id=envelope.correlation_id
        )
        
        return StageResult(continue_pipeline=True, envelope=new_env, emitted_events=[sized_event])


class CircuitBreakerStage(IPipelineStage):
    def __init__(self, circuit_breaker: CircuitBreakerEngine):
        self._cb = circuit_breaker
        
    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, ExecuteTradeCommand):
            return StageResult.continue_with(envelope)
            
        if self._cb.is_tripped(envelope.payload.strategy_id):
            reject_event = TradeRejectedByCircuitBreaker(
                strategy_id=envelope.payload.strategy_id,
                symbol=envelope.payload.symbol,
                requested_value=envelope.payload.estimated_value,
                reason="Strategy circuit breaker is tripped."
            )
            return StageResult.halt("Circuit Breaker Tripped", events=[reject_event])
            
        return StageResult.continue_with(envelope)


import MetaTrader5 as mt5
import logging
import time

logger = logging.getLogger(__name__)


class TradeThrottleStage(IPipelineStage):
    """Cap live trade attempts over rolling one-hour windows.

    A throttle slot is reserved before execution and must be released again
    when the broker/portfolio rejects the order without any fill. Filled orders
    keep their slot until the rolling window expires.
    """

    def __init__(
        self,
        max_global_per_hour: int = 5,
        max_symbol_per_hour: int = 2,
        clock=time.time,
        emit_structured_logs: bool = True,
    ):
        self._max_global = int(max_global_per_hour)
        self._max_symbol = int(max_symbol_per_hour)
        self._clock = clock
        self._emit_structured_logs = emit_structured_logs
        self._global_times = deque()
        self._symbol_times = defaultdict(deque)
        self._window_seconds = 3600

    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, (SizePositionCommand, ExecuteTradeCommand)):
            return StageResult.continue_with(envelope)

        cmd = envelope.payload
        now = float(self._clock())
        self._prune(self._global_times, now)
        self._prune(self._symbol_times[cmd.symbol], now)

        if self._max_global > 0 and len(self._global_times) >= self._max_global:
            return self._reject(
                envelope,
                f"Trade throttle: global hourly limit reached ({len(self._global_times)}/{self._max_global})",
            )

        if self._max_symbol > 0 and len(self._symbol_times[cmd.symbol]) >= self._max_symbol:
            return self._reject(
                envelope,
                f"Trade throttle: {cmd.symbol} hourly limit reached "
                f"({len(self._symbol_times[cmd.symbol])}/{self._max_symbol})",
            )

        self._global_times.append(now)
        self._symbol_times[cmd.symbol].append(now)
        return StageResult.continue_with(envelope)

    def release_for_symbol(self, symbol: str, reason: str = "") -> bool:
        """Return one reserved throttle slot for a no-fill attempt."""
        symbol_times = self._symbol_times.get(symbol)
        if not symbol_times:
            return False

        symbol_times.pop()
        if not symbol_times:
            self._symbol_times.pop(symbol, None)
        if self._global_times:
            self._global_times.pop()

        suffix = f": {reason}" if reason else ""
        logger.info("[TradeThrottle] Released no-fill slot for %s%s", symbol, suffix)
        return True

    def _prune(self, timestamps: deque, now: float) -> None:
        cutoff = now - self._window_seconds
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    def _reject(self, envelope: MessageEnvelope, reason: str) -> StageResult:
        cmd = envelope.payload
        logger.warning("[TradeThrottle] BLOCKED %s: %s", cmd.symbol, reason)
        if self._emit_structured_logs:
            try:
                from gqos.common.structured_logger import log_structured_event

                log_structured_event(
                    event_type="RISK_CHECK_BLOCKED",
                    decision_id=getattr(cmd, "decision_id", ""),
                    symbol=cmd.symbol,
                    side=str(cmd.direction),
                    status="BLOCKED",
                    reason=reason,
                )
            except Exception as exc:
                logger.warning("[TradeThrottle] Failed to emit structured log: %s", exc)

        reject_event = TradeRejectedByCircuitBreaker(
            strategy_id=cmd.strategy_id,
            symbol=cmd.symbol,
            requested_value=Decimal("0"),
            reason=reason,
        )
        return StageResult.halt("Trade throttle limit reached", events=[reject_event])


class AccountLossGuardStage(IPipelineStage):
    """Block new entries when account-level drawdown has already breached limits."""

    def __init__(
        self,
        reference_balance: Decimal,
        max_realized_drawdown_pct: Decimal = Decimal("0.10"),
        max_equity_drawdown_pct: Decimal = Decimal("0.12"),
        mt5_module=mt5,
        emit_structured_logs: bool = True,
    ):
        if reference_balance <= 0:
            raise ValueError("reference_balance must be positive")
        self._reference_balance = Decimal(str(reference_balance))
        self._max_realized_drawdown_pct = Decimal(str(max_realized_drawdown_pct))
        self._max_equity_drawdown_pct = Decimal(str(max_equity_drawdown_pct))
        self._mt5 = mt5_module
        self._emit_structured_logs = emit_structured_logs

    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        payload = envelope.payload
        if not isinstance(payload, (SizePositionCommand, ExecuteTradeCommand)):
            return StageResult.continue_with(envelope)

        acc = self._mt5.account_info()
        if acc is None:
            reason = "Account loss guard cannot read MT5 account_info"
            logger.error(f"[AccountLossGuard] BLOCKED: {reason}")
            return self._reject(envelope, reason)

        balance = Decimal(str(getattr(acc, "balance", "0")))
        equity = Decimal(str(getattr(acc, "equity", balance)))
        realized_dd_pct = max(Decimal("0"), (self._reference_balance - balance) / self._reference_balance)
        equity_dd_pct = max(Decimal("0"), (self._reference_balance - equity) / self._reference_balance)

        symbol = getattr(payload, "symbol", "?")
        logger.info(
            "[AccountLossGuard] %s balance=%s equity=%s realized_dd=%.2f%% equity_dd=%.2f%% "
            "limits(realized=%.2f%%, equity=%.2f%%)",
            symbol,
            balance,
            equity,
            float(realized_dd_pct * 100),
            float(equity_dd_pct * 100),
            float(self._max_realized_drawdown_pct * 100),
            float(self._max_equity_drawdown_pct * 100),
        )

        if realized_dd_pct >= self._max_realized_drawdown_pct:
            reason = (
                f"Realized drawdown {realized_dd_pct:.2%} >= "
                f"{self._max_realized_drawdown_pct:.2%} "
                f"(balance {balance} vs reference {self._reference_balance})"
            )
            logger.warning(f"[AccountLossGuard] BLOCKED {symbol}: {reason}")
            return self._reject(envelope, reason)

        if equity_dd_pct >= self._max_equity_drawdown_pct:
            reason = (
                f"Equity drawdown {equity_dd_pct:.2%} >= "
                f"{self._max_equity_drawdown_pct:.2%} "
                f"(equity {equity} vs reference {self._reference_balance})"
            )
            logger.warning(f"[AccountLossGuard] BLOCKED {symbol}: {reason}")
            return self._reject(envelope, reason)

        return StageResult.continue_with(envelope)

    def _reject(self, envelope: MessageEnvelope, reason: str) -> StageResult:
        payload = envelope.payload
        symbol = getattr(payload, "symbol", "")
        side = str(getattr(payload, "direction", ""))
        decision_id = getattr(payload, "decision_id", "")

        if self._emit_structured_logs:
            try:
                from gqos.common.structured_logger import log_structured_event

                metadata = {
                    "reference_balance": float(self._reference_balance),
                    "max_realized_dd_pct": float(self._max_realized_drawdown_pct),
                    "max_equity_dd_pct": float(self._max_equity_drawdown_pct),
                }
                log_structured_event(
                    event_type="SIGNAL_SKIPPED",
                    decision_id=decision_id,
                    symbol=symbol,
                    side=side,
                    status="SKIPPED",
                    reason=reason,
                    metadata=metadata,
                )
                log_structured_event(
                    event_type="RISK_CHECK_BLOCKED",
                    decision_id=decision_id,
                    symbol=symbol,
                    side=side,
                    status="BLOCKED",
                    reason=f"AccountLossGuard: {reason}",
                    metadata=metadata,
                )
            except Exception as e:
                logger.warning(f"[AccountLossGuard] Failed to emit structured log: {e}")

        reject_event = TradeRejectedByCircuitBreaker(
            strategy_id=getattr(payload, "strategy_id", ""),
            symbol=symbol,
            requested_value=getattr(payload, "estimated_value", Decimal("0")),
            reason=reason,
        )
        return StageResult.halt("Account loss guard tripped", events=[reject_event])

CORRELATION_GROUPS = {
    "METALS":     ["XAUUSD", "XAGUSD"],
    "US_EQUITY":  ["NAS100", "US500", "USTEC", "US30", "GER40"],
    "EUR_BLOCK":  ["EURUSD", "GBPUSD", "EURGBP"],
    "CRYPTO":     ["BTCUSD", "ETHUSD", "XRPUSD", "SOLUSD"],
    "AUD_BLOCK":  ["AUDUSD", "AUDCAD", "NZDUSD"],
    "OIL_BLOCK":  ["USOIL", "USDCAD"],
}


def _canonical_symbol(symbol: str) -> str:
    symbol = str(symbol or "").upper()
    if symbol.endswith(".M"):
        symbol = symbol[:-2]
    elif symbol.endswith("M") and len(symbol) > 3:
        symbol = symbol[:-1]
    return symbol


def _correlation_group(symbol: str) -> tuple[Optional[str], set[str]]:
    canonical = _canonical_symbol(symbol)
    for group_name, group_symbols in CORRELATION_GROUPS.items():
        group_set = {_canonical_symbol(s) for s in group_symbols}
        if canonical in group_set:
            return group_name, group_set
    return None, set()


def _calc_risk_usd(symbol: str, sl_distance: float, volume: float) -> float:
    """
    คำนวณความเสี่ยงเป็น USD โดยใช้ tick_value จริงจาก MT5
    แทน hardcode * 100 ที่ผิดสำหรับ Indices/Crypto

    Formula: risk_usd = (sl_distance / tick_size) * tick_value * volume
    """
    try:
        info = mt5.symbol_info(symbol)
        if info is None:
            # fallback สำหรับ symbol ที่หาไม่เจอ
            return sl_distance * volume * 100

        tick_size  = info.trade_tick_size   # minimum price move
        tick_value = info.trade_tick_value  # USD per tick per lot

        if tick_size <= 0 or tick_value <= 0:
            return sl_distance * volume * 100

        risk = (sl_distance / tick_size) * tick_value * volume
        return risk

    except Exception:
        return sl_distance * volume * 100


class ExposureStage(IPipelineStage):
    def __init__(
        self,
        exposure_engine: ExposureEngine,
        max_positions: int = 3,
        max_portfolio_risk_pct: float = 0.06,
        max_correlated_positions_per_group: int = 3,
    ):
        self._exposure = exposure_engine
        self._max_positions = max_positions
        self._max_portfolio_risk_pct = max_portfolio_risk_pct
        self._max_correlated_positions_per_group = int(max_correlated_positions_per_group)

    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, ExecuteTradeCommand):
            return StageResult.continue_with(envelope)

        cmd = envelope.payload
        pos = mt5.positions_get() or []
        acc = mt5.account_info()

        if acc is not None:

            # Rule 1: Max Open Positions
            if len(pos) >= self._max_positions:
                reject_event = TradeRejectedByExposureLimit(
                    strategy_id=cmd.strategy_id, symbol=cmd.symbol,
                    requested_value=cmd.estimated_value,
                    limit_type="MAX_POSITIONS",
                    reason=f"Max {self._max_positions} positions reached"
                )
                logger.warning(
                    f"[ExposureStage] BLOCKED {cmd.symbol}: "
                    f"max positions {len(pos)}/{self._max_positions}"
                )
                try:
                    from gqos.common.structured_logger import log_structured_event
                    log_structured_event(
                        event_type="SIGNAL_SKIPPED",
                        decision_id=getattr(cmd, "decision_id", ""),
                        symbol=cmd.symbol,
                        side=str(cmd.direction),
                        status="SKIPPED",
                        reason=f"Max {self._max_positions} positions reached"
                    )
                    log_structured_event(
                        event_type="RISK_CHECK_BLOCKED",
                        decision_id=getattr(cmd, "decision_id", ""),
                        symbol=cmd.symbol,
                        side=str(cmd.direction),
                        status="BLOCKED",
                        reason=f"Max {self._max_positions} positions reached"
                    )
                except Exception:
                    pass
                return StageResult.halt("Max positions reached", events=[reject_event])

            # Rule 2: Total Portfolio Risk Cap
            # ─── แก้: ใช้ _calc_risk_usd แทน hardcode * 100 ───────────
            total_risk = sum(
                _calc_risk_usd(
                    p.symbol,
                    abs(p.price_open - p.sl),
                    p.volume
                )
                for p in pos if p.sl > 0
            )
            
            logger.warning(f"[ExposureStage DEBUG] total_risk={total_risk} from {len(pos)} positions")

            incoming_risk = 0.0
            if cmd.stop_loss and cmd.quantity:
                try:
                    from data.mt5_client import mt5_client
                    resolved   = mt5_client.resolve_symbol(cmd.symbol)
                    tick       = mt5.symbol_info_tick(resolved)
                    if tick:
                        exec_price    = tick.ask if "BUY" in str(cmd.direction) else tick.bid
                        sl_distance   = abs(exec_price - float(cmd.stop_loss))
                        incoming_risk = _calc_risk_usd(
                            resolved,
                            sl_distance,
                            float(cmd.quantity)
                        )
                        logger.warning(f"[ExposureStage DEBUG] {cmd.symbol} incoming_risk={incoming_risk} (sl_dist={sl_distance}, qty={cmd.quantity})")
                except Exception as e:
                    logger.warning(f"[ExposureStage] Could not estimate incoming risk: {e}")
            # ────────────────────────────────────────────────────────────

            balance = float(acc.balance) if isinstance(getattr(acc, "balance", None), Number) else 0.0
            total_risk_value = float(total_risk) if isinstance(total_risk, Number) else 0.0
            incoming_risk_value = float(incoming_risk) if isinstance(incoming_risk, Number) else 0.0
            risk_limit_pct = float(self._max_portfolio_risk_pct)

            max_risk = balance * risk_limit_pct
            total_risk_pct = (total_risk_value / balance * 100) if balance else 0
            incoming_risk_pct = (incoming_risk_value / balance * 100) if balance else 0
            budget_pct = risk_limit_pct * 100
            remaining_pct = budget_pct - total_risk_pct - incoming_risk_pct
            
            d_id = getattr(cmd, "decision_id", "")
            prefix = f"[{d_id}] " if d_id else ""

            logger.info(
                f"{prefix}ExposureStage -> Portfolio Risk: {total_risk_pct:.2f}% | "
                f"Incoming: {incoming_risk_pct:.2f}% | Budget: {budget_pct:.2f}% | "
                f"Remaining: {remaining_pct:.2f}%"
            )

            if (total_risk_value + incoming_risk_value) > max_risk:
                reject_event = TradeRejectedByExposureLimit(
                    strategy_id=cmd.strategy_id, symbol=cmd.symbol,
                    requested_value=cmd.estimated_value,
                    limit_type="MAX_PORTFOLIO_RISK",
                    reason=(
                        f"Portfolio risk ${total_risk_value+incoming_risk_value:.0f} "
                        f"> ${max_risk:.0f} "
                        f"({budget_pct:.0f}%)"
                    )
                )
                logger.warning(
                    f"{prefix}ExposureStage BLOCKED {cmd.symbol}: "
                    f"risk ${total_risk_value+incoming_risk_value:.0f} > max ${max_risk:.0f}"
                )
                try:
                    from gqos.common.structured_logger import log_structured_event
                    log_structured_event(
                        event_type="SIGNAL_SKIPPED",
                        decision_id=d_id,
                        symbol=cmd.symbol,
                        side=str(cmd.direction),
                        status="SKIPPED",
                        reason=f"Risk Cap Exceeded ({budget_pct:.0f}%)"
                    )
                    log_structured_event(
                        event_type="RISK_CHECK_BLOCKED",
                        decision_id=d_id,
                        symbol=cmd.symbol,
                        side=str(cmd.direction),
                        status="BLOCKED",
                        reason=f"Risk Cap Exceeded ({budget_pct:.0f}%)"
                    )
                except Exception:
                    pass
                return StageResult.halt("Portfolio risk cap exceeded", events=[reject_event])

            # Rule 3: Correlation Group Cap
            try:
                from data.mt5_client import mt5_client
                mt5_symbol = mt5_client.resolve_symbol(cmd.symbol)
            except Exception:
                mt5_symbol = cmd.symbol

            open_symbols = {_canonical_symbol(p.symbol) for p in pos}
            group_name, group_symbols = _correlation_group(mt5_symbol)
            if group_name and self._max_correlated_positions_per_group > 0:
                conflicts = sorted(open_symbols.intersection(group_symbols))
                if len(conflicts) >= self._max_correlated_positions_per_group:
                    reason = (
                        f"Correlation group {group_name} cap reached "
                        f"({len(conflicts)}/{self._max_correlated_positions_per_group}): {conflicts}"
                    )
                    reject_event = TradeRejectedByExposureLimit(
                        strategy_id=cmd.strategy_id,
                        symbol=cmd.symbol,
                        requested_value=cmd.estimated_value,
                        limit_type="CORRELATION_GROUP",
                        reason=reason,
                    )
                    logger.warning(f"{prefix}ExposureStage BLOCKED {cmd.symbol}: {reason}")
                    try:
                        from gqos.common.structured_logger import log_structured_event
                        log_structured_event(
                            event_type="RISK_CHECK_BLOCKED",
                            decision_id=d_id,
                            symbol=cmd.symbol,
                            side=str(cmd.direction),
                            status="BLOCKED",
                            reason=reason,
                        )
                    except Exception:
                        pass
                    return StageResult.halt("Correlation group limit", events=[reject_event])

        # Per-trade exposure check (existing engine)
        is_allowed, code, reason = self._exposure.evaluate_trade(cmd)
        
        d_id = getattr(cmd, "decision_id", "")
        if not is_allowed:
            logger.warning(f"[ExposureStage] {cmd.symbol} BLOCKED by {code}: {reason}")
            reject_event = TradeRejectedByExposureLimit(
                strategy_id=cmd.strategy_id, symbol=cmd.symbol,
                requested_value=cmd.estimated_value,
                limit_type=code, reason=reason
            )
            
            try:
                from gqos.common.structured_logger import log_structured_event
                log_structured_event(
                    event_type="RISK_CHECK_BLOCKED",
                    decision_id=d_id,
                    symbol=cmd.symbol,
                    side=str(cmd.direction),
                    status="BLOCKED",
                    reason=f"{code}: {reason}"
                )
            except Exception:
                pass
                
            return StageResult.halt("Exposure Limit Exceeded", events=[reject_event])

        try:
            from gqos.common.structured_logger import log_structured_event
            log_structured_event(
                event_type="RISK_CHECK_PASSED",
                decision_id=d_id,
                symbol=cmd.symbol,
                side=str(cmd.direction),
                status="PASSED",
                reason="All exposure limits passed"
            )
        except Exception:
            pass

        return StageResult.continue_with(envelope)


class RiskBudgetStage(IPipelineStage):
    """
    NOTE: every successful allocation here MUST be released via
    release_for_symbol() when the corresponding position closes (wired in
    scripts/run_gqos_live.py's on_position_closed handler). Without that,
    utilized_capacity only ever grows and the budget silently leaks to zero,
    permanently blocking all new trades at this stage with "Insufficient Risk
    Budget" — confirmed live on 2026-06-29: remaining was ~$7 out of a ~$187k
    budget after ~1.5 days of uptime because nothing ever called
    release_allocation() in the live pipeline.
    """
    def __init__(self, risk_budget: RiskBudgetEngine):
        self._budget = risk_budget
        from collections import defaultdict, deque
        self._open_allocations = defaultdict(deque)

    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, ExecuteTradeCommand):
            return StageResult.continue_with(envelope)

        cmd = envelope.payload
        from gqos.risk.models import AllocationRequest
        import uuid

        alloc_id = str(uuid.uuid4())
        context.data['risk_allocation_id'] = alloc_id

        req = AllocationRequest(
            budget_id=cmd.strategy_id,
            strategy_id=cmd.strategy_id,
            requested_amount=cmd.estimated_value,
            allocation_id=alloc_id
        )
        result, budget, _ = self._budget.request_allocation(req)
        if result.success:
            self._open_allocations[cmd.symbol].append(alloc_id)
            updated_cmd = replace(cmd, risk_allocation_id=alloc_id)
            updated_env = MessageEnvelope(
                message_id=envelope.message_id,
                payload=updated_cmd,
                version=envelope.version,
                timestamp=envelope.timestamp,
                correlation_id=envelope.correlation_id,
                trace_id=envelope.trace_id,
                run_id=envelope.run_id,
                sequence_number=envelope.sequence_number,
            )
            alloc_event = RiskBudgetAllocated(
                budget_id=cmd.strategy_id,
                allocation_id=req.allocation_id,
                strategy_id=cmd.strategy_id,
                allocated_amount=result.amount_allocated,
                new_utilized_capacity=result.new_utilized_capacity,
                total_capacity=result.total_capacity
            )
            return StageResult(continue_pipeline=True, envelope=updated_env, emitted_events=[alloc_event])
        else:
            reject_event = TradeRejectedByRiskEvent(
                strategy_id=cmd.strategy_id,
                symbol=cmd.symbol,
                requested_value=cmd.estimated_value,
                reason=f"Insufficient Risk Budget: {result.reason}"
            )
            logger.warning(f"[RiskBudgetStage] {cmd.symbol} BLOCKED: {result.reason}")
            return StageResult.halt("Insufficient Risk Budget", events=[reject_event])

    def release_for_symbol(self, symbol: str) -> bool:
        """Release the oldest open allocation for `symbol` back to the budget.
        Call this when a position on `symbol` closes, regardless of outcome."""
        queue = self._open_allocations.get(symbol)
        if not queue:
            logger.warning(f"[RiskBudgetStage] release_for_symbol: no tracked allocation for {symbol}")
            return False
        alloc_id = queue.popleft()
        success, budget, amount = self._budget.release_allocation(alloc_id)
        if success:
            logger.info(f"[RiskBudgetStage] Released ${amount} risk budget for {symbol} (alloc={alloc_id})")
        else:
            logger.warning(f"[RiskBudgetStage] Failed to release allocation {alloc_id} for {symbol}")
        return success

    def release_for_allocation_id(self, allocation_id: str) -> bool:
        success, budget, amount = self._budget.release_allocation(allocation_id)
        if not success:
            logger.warning(f"[RiskBudgetStage] Failed to release allocation {allocation_id}")
            return False

        for symbol, queue in list(self._open_allocations.items()):
            try:
                queue.remove(allocation_id)
            except ValueError:
                continue
            if not queue:
                self._open_allocations.pop(symbol, None)
            break

        logger.info(f"[RiskBudgetStage] Released ${amount} risk budget (alloc={allocation_id})")
        return True


class PortfolioReservationStage(IPipelineStage):
    def __init__(self, manager: PortfolioManager):
        self._manager = manager
        
    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, ExecuteTradeCommand):
            return StageResult.continue_with(envelope)
            
        cmd = envelope.payload
        import uuid
        alloc_id = str(uuid.uuid4())
        context.data['portfolio_allocation_id'] = alloc_id
        
        success, reason = self._manager.reserve_cash(
            cmd.strategy_id,
            cmd.estimated_value,
            symbol=cmd.symbol,
            allocation_id=alloc_id,
        )
        if not success:
            reject_event = TradeRejectedByPortfolioEvent(
                strategy_id=cmd.strategy_id,
                symbol=cmd.symbol,
                requested_amount=cmd.estimated_value,
                reason=reason
            )
            return StageResult.halt(f"Portfolio Reservation Failed: {reason}", events=[reject_event])
            
        alloc = self._manager.state.allocations[cmd.strategy_id]
        updated_cmd = replace(cmd, portfolio_allocation_id=alloc_id)
        updated_env = MessageEnvelope(
            message_id=envelope.message_id,
            payload=updated_cmd,
            version=envelope.version,
            timestamp=envelope.timestamp,
            correlation_id=envelope.correlation_id,
            trace_id=envelope.trace_id,
            run_id=envelope.run_id,
            sequence_number=envelope.sequence_number,
        )
        reserve_event = CashReservedEvent(
            strategy_id=cmd.strategy_id,
            amount=cmd.estimated_value,
            allocation_id=alloc_id,
            new_reserved_cash=alloc.reserved_cash,
            new_buying_power=alloc.buying_power
        )
        return StageResult(continue_pipeline=True, envelope=updated_env, emitted_events=[reserve_event])

    def release_for_symbol(self, symbol: str) -> bool:
        """Release the oldest tracked cash reservation for `symbol`.
        Call this when the position closes or the broker rejects before fill."""
        release_event = self.release_event_for_symbol(symbol, "Position Closed")
        return release_event is not None

    def release_event_for_symbol(self, symbol: str, reason: str) -> Optional[CashReleasedEvent]:
        success, release_reason, reservation = self._manager.release_cash_for_symbol(symbol)
        if success and reservation is not None:
            logger.info(
                f"[PortfolioReservationStage] Released ${reservation.amount} "
                f"reserved cash for {symbol} (alloc={reservation.allocation_id})"
            )
            alloc = self._manager.state.allocations[reservation.strategy_id]
            return CashReleasedEvent(
                strategy_id=reservation.strategy_id,
                amount=reservation.amount,
                allocation_id=reservation.allocation_id,
                new_reserved_cash=alloc.reserved_cash,
                new_buying_power=alloc.buying_power,
                reason=reason,
            )
        elif release_reason:
            logger.warning(f"[PortfolioReservationStage] release_for_symbol: {release_reason}")
        return None

    def release_event_for_allocation_id(self, allocation_id: str, reason: str) -> Optional[CashReleasedEvent]:
        success, release_reason, reservation = self._manager.release_cash_for_allocation(allocation_id)
        if success and reservation is not None:
            logger.info(
                f"[PortfolioReservationStage] Released ${reservation.amount} "
                f"reserved cash (alloc={allocation_id})"
            )
            alloc = self._manager.state.allocations[reservation.strategy_id]
            return CashReleasedEvent(
                strategy_id=reservation.strategy_id,
                amount=reservation.amount,
                allocation_id=reservation.allocation_id,
                new_reserved_cash=alloc.reserved_cash,
                new_buying_power=alloc.buying_power,
                reason=reason,
            )
        elif release_reason:
            logger.warning(f"[PortfolioReservationStage] release_for_allocation_id: {release_reason}")
        return None


class ExecutionStage(IPipelineStage):
    def __init__(self, execution_bus: ICommandBus, manager: PortfolioManager):
        self._execution_bus = execution_bus
        self._manager = manager
        
    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, ExecuteTradeCommand):
            return StageResult.continue_with(envelope)
            
        cmd = envelope.payload
        
        try:
            self._execution_bus.dispatch(envelope)
            return StageResult.continue_with(envelope)
        except Exception as e:
            alloc_id = context.data.get('portfolio_allocation_id', 'unknown')
            self._manager.release_cash(cmd.strategy_id, cmd.estimated_value)
            
            alloc = self._manager.state.allocations[cmd.strategy_id]
            release_event = CashReleasedEvent(
                strategy_id=cmd.strategy_id,
                amount=cmd.estimated_value,
                allocation_id=alloc_id,
                new_reserved_cash=alloc.reserved_cash,
                new_buying_power=alloc.buying_power,
                reason=f"Execution Failed: {str(e)}"
            )
            return StageResult.halt(f"Execution Failed: {str(e)}", events=[release_event])
