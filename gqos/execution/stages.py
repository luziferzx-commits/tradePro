from typing import Optional
from decimal import Decimal
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
            # We need settled cash to calculate NAV, but the snapshot already separates them.
            # PortfolioManager tracks allocated_capital (settled + realized).
            # We just need unrealized_pnl to add to total_equity.
            try:
                # We can calculate strategy NAV or just get unrealized PnL.
                alloc = self._manager.state.allocations.get(strategy_id)
                settled_cash = alloc.allocated_capital if alloc else Decimal('0')
                val = self._valuation_engine.calculate_strategy_nav(strategy_id, settled_cash)
                unrealized_pnl = val.total_unrealized_pnl
            except Exception as e:
                # If pricing fails, we might want to halt or proceed with 0 MTM.
                # For safety, let's halt if MTM fails, since Kelly sizing depends on accurate MTM.
                return StageResult.halt(f"Valuation Failed: {str(e)}", events=[])
                
        snapshot = self._manager.generate_snapshot(strategy_id, unrealized_pnl)
        
        # Inject into context
        context.snapshot = snapshot
        
        # We don't emit an event here by default to reduce noise, unless needed.
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

logger = logging.getLogger(__name__)

CORRELATION_GROUPS = {
    "METALS":    ["XAUUSDm", "XAGUSDm"],
    "US_EQUITY": ["NAS100m", "US500m", "USTECm"],
    "EUR_BLOCK": ["EURUSDm", "GBPUSDm"],
    "CRYPTO":    ["BTCUSDm", "ETHUSDm"],
}

class ExposureStage(IPipelineStage):
    def __init__(self, exposure_engine: ExposureEngine, max_positions: int = 3, max_portfolio_risk_pct: float = 0.06):
        self._exposure = exposure_engine
        self._max_positions = max_positions
        self._max_portfolio_risk_pct = max_portfolio_risk_pct

    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, ExecuteTradeCommand):
            return StageResult.continue_with(envelope)

        cmd = envelope.payload

        # ---- PORTFOLIO-LEVEL RISK GUARD ----
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
                logger.warning(f"[ExposureStage] BLOCKED {cmd.symbol}: max positions {len(pos)}/{self._max_positions}")
                return StageResult.halt("Max positions reached", events=[reject_event])

            # Rule 2: Total Portfolio Risk Cap (6%)
            total_risk = sum(
                abs(p.price_open - p.sl) * p.volume * 100
                for p in pos if p.sl > 0
            )
            incoming_risk = 0.0
            if cmd.stop_loss and cmd.quantity:
                try:
                    from data.mt5_client import mt5_client
                    resolved = mt5_client.resolve_symbol(cmd.symbol)
                    tick = mt5.symbol_info_tick(resolved)
                    if tick:
                        exec_price = tick.ask if "BUY" in str(cmd.direction) else tick.bid
                        incoming_risk = abs(exec_price - float(cmd.stop_loss)) * float(cmd.quantity) * 100
                except Exception as e:
                    logger.warning(f"[ExposureStage] Could not estimate incoming risk: {e}")

            if (total_risk + incoming_risk) > (acc.balance * self._max_portfolio_risk_pct):
                reject_event = TradeRejectedByExposureLimit(
                    strategy_id=cmd.strategy_id, symbol=cmd.symbol,
                    requested_value=cmd.estimated_value,
                    limit_type="MAX_PORTFOLIO_RISK",
                    reason=f"Portfolio risk {total_risk+incoming_risk:.0f} > {acc.balance * self._max_portfolio_risk_pct:.0f} (6%)"
                )
                logger.warning(f"[ExposureStage] BLOCKED {cmd.symbol}: portfolio risk cap")
                return StageResult.halt("Portfolio risk cap exceeded", events=[reject_event])

            # Rule 3: Correlation Group Cap
            try:
                from data.mt5_client import mt5_client
                mt5_symbol = mt5_client.resolve_symbol(cmd.symbol)
            except Exception:
                mt5_symbol = cmd.symbol

            open_symbols = {p.symbol for p in pos}
            for group_name, group_symbols in CORRELATION_GROUPS.items():
                if mt5_symbol in group_symbols:
                    conflict = open_symbols.intersection(set(group_symbols))
                    if conflict:
                        reject_event = TradeRejectedByExposureLimit(
                            strategy_id=cmd.strategy_id, symbol=cmd.symbol,
                            requested_value=cmd.estimated_value,
                            limit_type="CORRELATION_GROUP",
                            reason=f"Correlated position already open in {group_name}: {conflict}"
                        )
                        logger.warning(f"[ExposureStage] BLOCKED {cmd.symbol}: correlation with {conflict}")
                        return StageResult.halt("Correlation group limit", events=[reject_event])

        # ---- PER-TRADE EXPOSURE CHECK (existing) ----
        is_allowed, code, reason = self._exposure.evaluate_trade(cmd)
        if not is_allowed:
            reject_event = TradeRejectedByExposureLimit(
                strategy_id=cmd.strategy_id, symbol=cmd.symbol,
                requested_value=cmd.estimated_value,
                limit_type=code, reason=reason
            )
            return StageResult.halt("Exposure Limit Exceeded", events=[reject_event])

        return StageResult.continue_with(envelope)


class RiskBudgetStage(IPipelineStage):
    def __init__(self, risk_budget: RiskBudgetEngine):
        self._budget = risk_budget
        
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
            alloc_event = RiskBudgetAllocated(
                budget_id=cmd.strategy_id,
                allocation_id=req.allocation_id,
                strategy_id=cmd.strategy_id,
                allocated_amount=result.amount_allocated,
                new_utilized_capacity=result.new_utilized_capacity,
                total_capacity=result.total_capacity
            )
            return StageResult(continue_pipeline=True, envelope=envelope, emitted_events=[alloc_event])
        else:
            reject_event = TradeRejectedByRiskEvent(
                strategy_id=cmd.strategy_id,
                symbol=cmd.symbol,
                requested_value=cmd.estimated_value,
                reason=f"Insufficient Risk Budget: {result.reason}"
            )
            return StageResult.halt("Insufficient Risk Budget", events=[reject_event])


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
        
        success, reason = self._manager.reserve_cash(cmd.strategy_id, cmd.estimated_value)
        if not success:
            reject_event = TradeRejectedByPortfolioEvent(
                strategy_id=cmd.strategy_id,
                symbol=cmd.symbol,
                requested_amount=cmd.estimated_value,
                reason=reason
            )
            return StageResult.halt(f"Portfolio Reservation Failed: {reason}", events=[reject_event])
            
        alloc = self._manager.state.allocations[cmd.strategy_id]
        reserve_event = CashReservedEvent(
            strategy_id=cmd.strategy_id,
            amount=cmd.estimated_value,
            allocation_id=alloc_id,
            new_reserved_cash=alloc.reserved_cash,
            new_buying_power=alloc.buying_power
        )
        return StageResult(continue_pipeline=True, envelope=envelope, emitted_events=[reserve_event])


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
            # Execution failed, release reserved cash
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
