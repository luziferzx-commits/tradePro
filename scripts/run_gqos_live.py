import os
import sys
import logging
import time
import threading
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import MetaTrader5 as mt5

from config.settings import settings

from gqos.messaging.bus import LocalCommandBus, LocalEventBus
from gqos.messaging.contracts import MessageEnvelope

from gqos.accounting.engine import AccountingEngine
from gqos.portfolio.manager import PortfolioManager
from gqos.risk.events import ExecuteTradeCommand, TradeExecutedEvent
from gqos.common.enums import TradeDirection

from gqos.live.events import OrderStatus, OrderUpdateEvent, ReconciliationFillEvent, HeartbeatEvent
from gqos.live.oms import OrderManagementSystem
from gqos.live.adapters.mt5_adapter import MT5BrokerAdapter
from gqos.live.safety import GlobalKillSwitch, HeartbeatMonitor
from gqos.live.persistence import LedgerSnapshotService
from gqos.live.engine import LiveTradingEngine
from gqos.live.alpha_worker import AlphaWorker
from gqos.live.position_monitor import PositionMonitor
from gqos.live.daily_scheduler import DailyReportScheduler
from gqos.live.process_lock import SingleInstanceLock
from gqos.ops.live_guard import LiveSessionGuard, build_startup_summary, get_daily_pnl

from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.policies import FixedFractionalPolicy, FixedRiskPolicy, DynamicScalingPolicy
from gqos.sizing.events import SizePositionCommand

from gqos.risk.circuit_breaker import CircuitBreaker
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.store import RiskBudgetStore
from gqos.risk.models import RiskBudget
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits

from gqos.execution.pipeline import TradingPipeline
from gqos.execution.stages import AccountLossGuardStage, TradeThrottleStage, SizingStage, CircuitBreakerStage, ExposureStage, RiskBudgetStage, PortfolioSnapshotStage, PortfolioReservationStage, ExecutionStage

# ─── Learning Loop imports ─────────────────────────────────────────
from gqos.learning.outcome_logger import outcome_logger
from gqos.learning.retrain_trigger import retrain_trigger
# ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("GQOS-Live")

class DefaultFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        return Decimal('0'), "USD"

class DefaultFxConverter:
    def convert(self, amount, from_curr, to_curr):
        return amount

def start_outcome_sync_worker(stop_event: threading.Event):
    def _loop():
        while not stop_event.is_set():
            try:
                from gqos.learning.mt5_outcome_sync import (
                    enrich_existing_outcomes,
                    sync_mt5_closed_deals_today,
                    sync_mt5_open_positions_to_pending,
                )
                restored = sync_mt5_open_positions_to_pending()
                synced = sync_mt5_closed_deals_today()
                enriched = enrich_existing_outcomes()
                if restored:
                    logger.info("[Learning] Periodic MT5 outcome sync restored %s open positions.", restored)
                    logger.info("[Learning] Pending outcome cache reloaded: %s entries.", outcome_logger.reload_pending())
                if synced:
                    logger.info("[Learning] Periodic MT5 outcome sync backfilled %s deals.", synced)
                if enriched:
                    logger.info("[Learning] Periodic MT5 outcome sync enriched %s outcomes.", enriched)
            except Exception as e:
                logger.warning("[Learning] Periodic MT5 outcome sync failed: %s", e)
            stop_event.wait(300)

    thread = threading.Thread(target=_loop, name="MT5OutcomeSync", daemon=True)
    thread.start()
    return thread

def start_continuous_market_sim_worker(stop_event: threading.Event):
    def _loop():
        while not stop_event.is_set():
            try:
                from gqos.learning.continuous_market_simulator import continuous_market_simulator
                stats = continuous_market_simulator.scan_once()
                if any(stats.values()):
                    logger.info("[ContinuousMarketSim] %s", stats)
                    try:
                        from gqos.learning.simulation_analyzer import build_simulation_recommendations
                        recs = build_simulation_recommendations()
                        logger.info(
                            "[SimulationAnalyzer] recommendations=%s virtual=%s missed=%s",
                            len(recs.get("recommendations", {})),
                            recs.get("virtual_rows", 0),
                            recs.get("missed_rows", 0),
                        )
                    except Exception as analyzer_error:
                        logger.warning("[SimulationAnalyzer] failed: %s", analyzer_error)
            except Exception as e:
                logger.warning("[ContinuousMarketSim] worker failed: %s", e)
            stop_event.wait(60)

    thread = threading.Thread(target=_loop, name="ContinuousMarketSim", daemon=True)
    thread.start()
    return thread

def main():
    logger.info("=========================================")
    logger.info("  GQOS LIVE ENGINE (INSTITUTIONAL MODE)  ")
    logger.info("=========================================")
    outcome_sync_stop = threading.Event()
    market_sim_stop = threading.Event()

    instance_lock = SingleInstanceLock("GQOS Live Engine", settings.LIVE_ENGINE_LOCK_PORT)
    if not instance_lock.acquire():
        logger.critical("Another GQOS live engine instance is already active. Exiting.")
        return
    
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        instance_lock.release()
        return
        
    acc_info = mt5.account_info()
    if not acc_info:
        logger.error("Could not retrieve MT5 account info.")
        instance_lock.release()
        return
        
    initial_capital = Decimal(str(acc_info.balance))
    logger.info(f"Connected to MT5. Initial Capital: ${initial_capital}")
    try:
        from gqos.learning.mt5_outcome_sync import (
            enrich_existing_outcomes,
            sync_mt5_closed_deals_today,
            sync_mt5_open_positions_to_pending,
        )
        restored = sync_mt5_open_positions_to_pending()
        synced = sync_mt5_closed_deals_today()
        enriched = enrich_existing_outcomes()
        if restored:
            logger.info("[Learning] Restored %s open MT5 positions into pending outcomes.", restored)
            logger.info("[Learning] Pending outcome cache reloaded: %s entries.", outcome_logger.reload_pending())
        if synced:
            logger.info("[Learning] Backfilled %s MT5 closed deals into live outcomes.", synced)
        if enriched:
            logger.info("[Learning] Enriched %s existing outcomes with pattern metadata.", enriched)
    except Exception as e:
        logger.warning("[Learning] MT5 outcome backfill skipped: %s", e)
    risk_reference_balance = Decimal(
        os.getenv("GQOS_RISK_REFERENCE_BALANCE", str(max(initial_capital, Decimal("10000"))))
    )
    max_realized_dd_pct = Decimal(os.getenv("GQOS_MAX_REALIZED_DD_PCT", "0.10"))
    max_equity_dd_pct = Decimal(os.getenv("GQOS_MAX_EQUITY_DD_PCT", "0.12"))
    logger.warning(
        "Account loss guard armed: reference=%s max_realized_dd=%.2f%% max_equity_dd=%.2f%%",
        risk_reference_balance,
        float(max_realized_dd_pct * 100),
        float(max_equity_dd_pct * 100),
    )

    cmd_bus = LocalCommandBus(logger)
    evt_bus = LocalEventBus(logger)
    
    accounting = AccountingEngine(evt_bus, DefaultFeeModel(), DefaultFxConverter())
    portfolio  = PortfolioManager("LivePort", initial_capital * 10)
    portfolio.allocate_capital("gqos_alpha_v1", initial_capital * 10)
    logger.info("Allocated virtual capital to strategies.")
    
    oms = OrderManagementSystem(evt_bus)
    
    def oms_callback(order_id, status, fill_qty, fill_price, msg):
        if status == "FILL":
            oms.apply_fill(order_id, fill_qty, fill_price)
        else:
            oms.update_order_status(order_id, OrderStatus(status), msg)
            
    adapter    = MT5BrokerAdapter(evt_bus, oms_callback)
    safety     = GlobalKillSwitch(oms, adapter)
    hb_monitor = HeartbeatMonitor(evt_bus, safety, timeout_seconds=60.0)
    
    snapshot_path = "gqos_ledger_state.json"
    persistence   = LedgerSnapshotService(snapshot_path)
    
    live_engine = LiveTradingEngine(
        evt_bus, cmd_bus, oms, adapter, safety, persistence, accounting, portfolio
    )
    
    sizing_engine = PositionSizingEngine()
    policy        = DynamicScalingPolicy(base_risk_fraction=Decimal('0.005'))
    cb_engine     = CircuitBreakerEngine()

    try:
        import yaml as _yaml
        with open("config/symbols.yaml", "r") as _f:
            _symbol_aliases = _yaml.safe_load(_f).get("symbol_aliases", {})
    except Exception:
        _symbol_aliases = {}
    
    asset_dir = AssetDirectory()
    for sym in ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "US500",
                "EURUSD", "GBPUSD", "USDJPY", "NAS100", "GER40", "USTEC",
                "AUDUSD", "USDCAD", "USOIL", "XRPUSD", "SOLUSD",
                "US30", "NZDUSD", "EURGBP", "AUDCAD"]:
        asset_dir.register_asset(AssetMetadata(sym,       "MIXED", "FX", sym))
        asset_dir.register_asset(AssetMetadata(f"{sym}m", "MIXED", "FX", sym))
        asset_dir.register_asset(AssetMetadata(f"{sym}.m","MIXED", "FX", sym))
        broker_symbol = _symbol_aliases.get(sym)
        if broker_symbol:
            asset_dir.register_asset(AssetMetadata(broker_symbol, "MIXED", "FX", sym))
        
    exposure = ExposureEngine(asset_dir, ExposureLimits(
        max_gross_exposure=initial_capital * 2,
        max_net_exposure=initial_capital * Decimal('1.5'),
        max_symbol_exposure=initial_capital * Decimal('0.5'),
        max_sector_exposure=initial_capital * 1,
        max_correlation_group_exposure=initial_capital * 1
    ))
    
    store = RiskBudgetStore()
    store.save(RiskBudget("gqos_alpha_v1", total_capacity=initial_capital * 20, utilized_capacity=Decimal('0')))
    risk_engine = RiskBudgetEngine(store)
    
    from gqos.risk.news_filter import NewsFilter
    from gqos.risk.news_stage import NewsGuardStage
    news_filter = NewsFilter(block_minutes=15)
    news_stage  = NewsGuardStage(news_filter)

    risk_budget_stage = RiskBudgetStage(risk_engine)
    portfolio_reservation_stage = PortfolioReservationStage(portfolio)
    trade_throttle_stage = TradeThrottleStage(
        max_global_per_hour=settings.TRADE_THROTTLE_MAX_GLOBAL_PER_HOUR,
        max_symbol_per_hour=settings.TRADE_THROTTLE_MAX_SYMBOL_PER_HOUR,
    )
    account_loss_guard_stage = AccountLossGuardStage(
        reference_balance=risk_reference_balance,
        max_realized_drawdown_pct=max_realized_dd_pct,
        max_equity_drawdown_pct=max_equity_dd_pct,
    )

    stages = [
        news_stage,
        account_loss_guard_stage,
        PortfolioSnapshotStage(portfolio),
        SizingStage(sizing_engine, policy),
        CircuitBreakerStage(cb_engine),
        ExposureStage(
            exposure,
            max_positions=settings.MAX_OPEN_POSITIONS,
            max_portfolio_risk_pct=0.08,
            max_correlated_positions_per_group=settings.MAX_CORRELATED_POSITIONS_PER_GROUP,
        ),
        trade_throttle_stage,
        risk_budget_stage,
        portfolio_reservation_stage,
        ExecutionStage(cmd_bus, portfolio)
    ]
    pipeline = TradingPipeline(stages, evt_bus)
    
    def handle_sizing_command(env: MessageEnvelope):
        result = pipeline.dispatch(env)
        logger.info(f"Pipeline Result: {result}")
        if isinstance(result, str) and result.startswith("Halted"):
            try:
                outcome_logger.discard_intent_by_symbol(env.payload.symbol)
            except Exception as e:
                logger.error(f"[Learning] Failed to discard intent on halt for {getattr(env.payload, 'symbol', '?')}: {e}")
            if "Halted at RiskBudgetStage" in result or "Halted at ExecutionStage" in result:
                trade_throttle_stage.release_for_symbol(env.payload.symbol, result)
        
    cmd_bus.register_handler(SizePositionCommand, handle_sizing_command)
    
    alpha_worker = AlphaWorker(cmd_bus)
    session_guard = LiveSessionGuard(alpha_worker=alpha_worker, circuit_breaker=cb_engine)
    startup_guard_reason = session_guard.enforce_startup_limits(float(initial_capital))
    alpha_worker.start()

    # ─── Dynamic Position Management ──────────────────────────────
    from strategy.indicators import IndicatorCalculator
    position_monitor = PositionMonitor(
        evidence_router=alpha_worker.evidence_router,
        mt5_client=alpha_worker.mt5_client,
        indicator_calculator=IndicatorCalculator,
        magic_number=settings.MAGIC_NUMBER,
        reduce_threshold=0.50,     # REDUCE เมื่อ edge เหลือ < 50%
        flip_confirm_candles=1,    # รอ 1 candle confirm ก่อน FLIP
        news_filter=news_filter    # Pass news filter for active management
    )
    position_monitor.set_cmd_bus(cmd_bus)
    position_monitor.set_event_bus(evt_bus)
    position_monitor.start()
    
    alpha_worker.position_monitor = position_monitor
    
    # ─── Daily Report Scheduler ───────────────────────────────────
    scheduler = DailyReportScheduler(report_hour_utc=8)
    scheduler.start()
    outcome_sync_thread = start_outcome_sync_worker(outcome_sync_stop)
    market_sim_thread = start_continuous_market_sim_worker(market_sim_stop)
    # ──────────────────────────────────────────────────────────────
    
    logger.info("Dynamic Position Management started.")
    # ──────────────────────────────────────────────────────────────

    # ─── Retrain Callback: reload ML model หลัง retrain เสร็จ ────────
    def on_retrain_complete():
        logger.info("♻️  Reloading ML models after retrain...")
        try:
            alpha_worker.predictor.reload()
            logger.info("✅ ML models reloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to reload ML models: {e}")

    retrain_trigger.on_retrain_complete = on_retrain_complete
    retrain_trigger.trigger_if_due()
    logger.info(
        f"Learning Loop armed. "
        f"Retrain trigger: every {retrain_trigger.retrain_threshold} live trades."
    )
    # ────────────────────────────────────────────────────────────────

    from notifications.telegram_notifier import notify_trade_executed, notify_trade_closed, send_telegram
    from database.logger import DatabaseLogger
    import uuid
    from datetime import datetime
    
    def on_trade_executed(env: MessageEnvelope):
        cmd = env.payload
        ticket_val = getattr(cmd, 'ticket', None)
        ticket_str = str(ticket_val) if ticket_val else "GQOS"
        
        notify_trade_executed(
            symbol=cmd.symbol,
            direction=cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction),
            lot=float(cmd.quantity),
            entry=float(cmd.execution_price),
            sl=0.0,
            tp=0.0,
            ticket=ticket_str,
            probability=0.0
        )
        # Log to Database
        try:
            db_ticket = str(ticket_val) if ticket_val else str(uuid.uuid4())
            DatabaseLogger.log_trade_execution(
                signal_id=None,
                ticket=db_ticket,
                symbol=cmd.symbol,
                direction=cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction),
                volume=float(cmd.quantity),
                open_price=float(cmd.execution_price),
                sl=0.0,
                tp=0.0,
                open_time=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to log trade execution to DB: {e}")
        
    last_closed_dir   = {}
    processed_realized_close_keys = set()

    def on_position_closed(env: MessageEnvelope):
        cmd = env.payload
        last_closed_dir[cmd.symbol] = (
            cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction)
        )
        pos_key = f"{cmd.strategy_id}_{cmd.symbol}"
        if pos_key in accounting.state.positions:
            logger.info(
                f"[Portfolio/RiskBudget] {cmd.symbol} partial close detected; "
                "keeping reservation until the position is fully closed."
            )
            return

        try:
            risk_budget_stage.release_for_symbol(cmd.symbol)
        except Exception as e:
            logger.error(f"[RiskBudget] Failed to release allocation for {cmd.symbol}: {e}")
        try:
            release_event = portfolio_reservation_stage.release_event_for_symbol(
                cmd.symbol,
                "Position Closed",
            )
            if release_event:
                evt_bus.publish(MessageEnvelope.create(
                    release_event,
                    version=env.version,
                    correlation_id=env.correlation_id,
                    trace_id=env.trace_id,
                    run_id=env.run_id,
                    sequence_number=env.sequence_number,
                ))
        except Exception as e:
            logger.error(f"[Portfolio] Failed to release cash reservation for {cmd.symbol}: {e}")

    _TERMINAL_NO_FILL_STATUSES = (OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.EXPIRED)

    def on_order_update(env: MessageEnvelope):
        evt = env.payload
        if evt.status in _TERMINAL_NO_FILL_STATUSES and evt.filled_quantity == Decimal('0'):
            try:
                if getattr(evt, "risk_allocation_id", ""):
                    released = risk_budget_stage.release_for_allocation_id(evt.risk_allocation_id)
                else:
                    released = risk_budget_stage.release_for_symbol(evt.symbol)

                if getattr(evt, "portfolio_allocation_id", ""):
                    release_event = portfolio_reservation_stage.release_event_for_allocation_id(
                        evt.portfolio_allocation_id,
                        f"Order {evt.status.value} Without Fill: {evt.message}",
                    )
                else:
                    release_event = portfolio_reservation_stage.release_event_for_symbol(
                        evt.symbol,
                        f"Order {evt.status.value} Without Fill: {evt.message}",
                    )
                if released:
                    logger.info(
                        f"[RiskBudget] Released allocation for {evt.symbol} "
                        f"after order reached {evt.status.value} ({evt.message})"
                    )
                if release_event:
                    evt_bus.publish(MessageEnvelope.create(
                        release_event,
                        version=env.version,
                        correlation_id=env.correlation_id,
                        trace_id=env.trace_id,
                        run_id=env.run_id,
                        sequence_number=env.sequence_number,
                    ))
                outcome_logger.discard_intent_by_symbol(evt.symbol)
                trade_throttle_stage.release_for_symbol(evt.symbol, f"Order {evt.status.value} without fill")
            except Exception as e:
                logger.error(f"[RiskBudget/Learning] Failed to release allocation/intent for {evt.symbol} on {evt.status.value}: {e}")
        elif evt.status in _TERMINAL_NO_FILL_STATUSES:
            logger.info(
                f"[Portfolio/RiskBudget] {evt.symbol} reached {evt.status.value} "
                f"with filled_quantity={evt.filled_quantity}; keeping reservation "
                "until the resulting position is fully closed."
            )

    def on_portfolio_reject(env: MessageEnvelope):
        evt = env.payload
        try:
            risk_budget_stage.release_for_symbol(evt.symbol)
            outcome_logger.discard_intent_by_symbol(evt.symbol)
            trade_throttle_stage.release_for_symbol(evt.symbol, "Portfolio Reservation rejection")
            logger.info(
                f"[RiskBudget/Learning] Released allocation + discarded intent "
                f"for {evt.symbol} after Portfolio Reservation rejection."
            )
        except Exception as e:
            logger.error(f"[RiskBudget/Learning] Failed to release/discard for {evt.symbol}: {e}")
        
    def on_realized_pnl(env: MessageEnvelope):
        cmd       = env.payload
        ticket    = getattr(cmd, 'ticket', None)
        exit_price = float(getattr(cmd, 'exit_price', 0.0))
        close_key = str(ticket) if ticket else f"{cmd.symbol}:{cmd.realized_pnl}:{exit_price}"
        if close_key in processed_realized_close_keys:
            logger.warning(
                f"[Learning/Telegram] Duplicate realized close event skipped: "
                f"{cmd.symbol} ticket={ticket} pnl={cmd.realized_pnl}"
            )
            return
        processed_realized_close_keys.add(close_key)

        acc       = mt5.account_info()
        balance   = acc.balance if acc else 0.0
        direction = last_closed_dir.get(cmd.symbol, "UNKNOWN")

        notify_trade_closed(
            ticket=str(ticket) if ticket else "UNKNOWN",
            symbol=cmd.symbol,
            direction=direction,
            profit=float(cmd.realized_pnl),
            rr=0.0,
            balance=float(balance)
        )
        
        # Log to Database
        try:
            if ticket:
                DatabaseLogger.log_trade_close(
                    ticket=ticket,
                    close_price=exit_price,
                    close_time=datetime.utcnow(),
                    pnl=float(cmd.realized_pnl)
                )
        except Exception as e:
            logger.error(f"Failed to log trade close to DB: {e}")

        # ─── Learning Loop: บันทึก outcome ───────────────────────────
        try:
            if ticket and str(ticket).isdigit():
                record = outcome_logger.on_trade_closed(
                    ticket=int(ticket),
                    realized_pnl=float(cmd.realized_pnl),
                    exit_price=exit_price,
                )
            else:
                record = outcome_logger.on_trade_closed_by_symbol(
                    symbol=cmd.symbol,
                    realized_pnl=float(cmd.realized_pnl),
                    exit_price=exit_price,
                )
            if record:
                outcome = "WIN" if float(cmd.realized_pnl) > 0 else "LOSS"
                retrain_trigger.on_trade_closed(
                    outcome=outcome,
                    symbol=cmd.symbol,
                    realized_pnl=float(cmd.realized_pnl),
                )
                stats = outcome_logger.get_stats()
                logger.info(
                    f"[Learning] {cmd.symbol} {outcome} pnl={cmd.realized_pnl:.2f} | "
                    f"Live stats: {stats['total']} trades "
                    f"WR={stats['win_rate']}% PnL={stats['total_pnl']:.2f}"
                )
        except Exception as e:
            logger.warning(f"[Learning] on_trade_closed failed: {e}")
        # ─────────────────────────────────────────────────────────────

        try:
            equity = float(getattr(acc, "equity", balance)) if acc else None
            guard_reason = session_guard.record_closed_trade(
                symbol=cmd.symbol,
                pnl=float(cmd.realized_pnl),
                balance=float(balance),
                equity=equity,
            )
            if guard_reason:
                logger.warning("[LiveGuard] %s", guard_reason)
                send_telegram(
                    f"<b>GQOS Live Guard</b>\n{guard_reason}\n"
                    "Existing positions will still be managed."
                )
        except Exception as e:
            logger.warning(f"[LiveGuard] failed to evaluate close event: {e}")

        # ─── Daily Loss Circuit Breaker ──────────────────────────────
        try:
            if balance > 0:
                daily_pnl, _, _, _ = get_daily_pnl()
                max_loss = balance * -settings.MAX_DAILY_LOSS_PCT
                if daily_pnl < max_loss:
                    logger.critical(f"Circuit Breaker TRIPPED! Daily Loss {daily_pnl:.2f} exceeded limit {max_loss:.2f}")
                    cb_engine.trip("DAILY_LOSS_LIMIT", f"Exceeded daily drawdown limit: {daily_pnl:.2f}")
        except Exception as e:
            logger.error(f"Failed to check daily loss circuit breaker: {e}")
        # ─────────────────────────────────────────────────────────────
        
    from gqos.risk.events import TradeExecutedEvent
    from gqos.accounting.events import PositionClosedEvent, RealizedPnLEmittedEvent
    from gqos.portfolio.events import TradeRejectedByPortfolioEvent
    
    evt_bus.subscribe(TradeExecutedEvent,     on_trade_executed)
    evt_bus.subscribe(PositionClosedEvent,    on_position_closed)
    evt_bus.subscribe(RealizedPnLEmittedEvent, on_realized_pnl)
    evt_bus.subscribe(OrderUpdateEvent,       on_order_update)
    evt_bus.subscribe(TradeRejectedByPortfolioEvent, on_portfolio_reject)
    
    from notifications.telegram_listener import TelegramCommandListener
    
    def shutdown_bot():
        import os
        logger.warning("🚨 EMERGENCY SHUTDOWN INITIATED")
        os._exit(0)
        
    cmd_listener = TelegramCommandListener(alpha_worker=alpha_worker, shutdown_callback=shutdown_bot)
    cmd_listener.start()

    send_telegram(build_startup_summary())
    if startup_guard_reason:
        logger.warning("[LiveGuard] %s", startup_guard_reason)
        send_telegram(
            f"<b>GQOS Startup Guard</b>\n{startup_guard_reason}\n"
            "Existing positions will still be managed."
        )
    live_engine.start()
    
    logger.info("GQOS Live Engine is completely booted and running. Press Ctrl+C to exit.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down GQOS...")
        scheduler.stop()
        outcome_sync_stop.set()
        market_sim_stop.set()
        outcome_sync_thread.join(timeout=2)
        market_sim_thread.join(timeout=2)
        position_monitor.stop()
        alpha_worker.stop()
        live_engine.stop()
        outcome_sync_stop.set()
        market_sim_stop.set()
        mt5.shutdown()
        instance_lock.release()
        logger.info("Shutdown complete.")
    finally:
        instance_lock.release()

if __name__ == "__main__":
    main()
