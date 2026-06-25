import os
import sys
import logging
import time
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

from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.policies import FixedFractionalPolicy
from gqos.sizing.events import SizePositionCommand

from gqos.risk.circuit_breaker import CircuitBreaker
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.store import RiskBudgetStore
from gqos.risk.models import RiskBudget
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits

from gqos.execution.pipeline import TradingPipeline
from gqos.execution.stages import SizingStage, CircuitBreakerStage, ExposureStage, RiskBudgetStage, PortfolioSnapshotStage, PortfolioReservationStage, ExecutionStage

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

def main():
    logger.info("=========================================")
    logger.info("  GQOS LIVE ENGINE (INSTITUTIONAL MODE)  ")
    logger.info("=========================================")
    
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        return
        
    acc_info = mt5.account_info()
    if not acc_info:
        logger.error("Could not retrieve MT5 account info.")
        return
        
    initial_capital = Decimal(str(acc_info.balance))
    logger.info(f"Connected to MT5. Initial Capital: ${initial_capital}")

    cmd_bus = LocalCommandBus(logger)
    evt_bus = LocalEventBus(logger)
    
    accounting = AccountingEngine(evt_bus, DefaultFeeModel(), DefaultFxConverter())
    portfolio  = PortfolioManager("LivePort", initial_capital)
    portfolio.allocate_capital("gqos_alpha_v1", initial_capital)
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
    policy        = FixedFractionalPolicy(fraction=Decimal('0.01'))
    cb_engine     = CircuitBreakerEngine()
    
    asset_dir = AssetDirectory()
    for sym in ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "US500", "EURUSD", "GBPUSD", "USDJPY", "NAS100", "GER40"]:
        asset_dir.register_asset(AssetMetadata(sym,       "MIXED", "FX", sym))
        asset_dir.register_asset(AssetMetadata(f"{sym}m", "MIXED", "FX", sym))
        asset_dir.register_asset(AssetMetadata(f"{sym}.m","MIXED", "FX", sym))
        
    exposure = ExposureEngine(asset_dir, ExposureLimits(
        max_gross_exposure=initial_capital * 10,
        max_net_exposure=initial_capital * 10,
        max_symbol_exposure=initial_capital * 5,
        max_sector_exposure=initial_capital * 10,
        max_correlation_group_exposure=initial_capital * 10
    ))
    
    store = RiskBudgetStore()
    store.save(RiskBudget("gqos_alpha_v1", total_capacity=initial_capital, utilized_capacity=Decimal('0')))
    risk_engine = RiskBudgetEngine(store)
    
    from gqos.risk.news_filter import NewsFilter
    from gqos.risk.news_stage import NewsGuardStage
    news_filter = NewsFilter(block_minutes=15)
    news_stage  = NewsGuardStage(news_filter)

    stages = [
        news_stage,
        PortfolioSnapshotStage(portfolio),
        SizingStage(sizing_engine, policy),
        CircuitBreakerStage(cb_engine),
        ExposureStage(exposure, max_positions=3, max_portfolio_risk_pct=0.06),
        RiskBudgetStage(risk_engine),
        PortfolioReservationStage(portfolio),
        ExecutionStage(cmd_bus, portfolio)
    ]
    pipeline = TradingPipeline(stages, evt_bus)
    
    def handle_sizing_command(env: MessageEnvelope):
        result = pipeline.dispatch(env)
        logger.info(f"Pipeline Result: {result}")
        
    cmd_bus.register_handler(SizePositionCommand, handle_sizing_command)
    
    alpha_worker = AlphaWorker(cmd_bus)
    alpha_worker.start()

    # ─── Retrain Callback: reload ML model หลัง retrain เสร็จ ────────
    def on_retrain_complete():
        logger.info("♻️  Reloading ML models after retrain...")
        try:
            alpha_worker.predictor.reload()
            logger.info("✅ ML models reloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to reload ML models: {e}")

    retrain_trigger.on_retrain_complete = on_retrain_complete
    logger.info(
        f"Learning Loop armed. "
        f"Retrain trigger: every {retrain_trigger.retrain_threshold} live trades."
    )
    # ────────────────────────────────────────────────────────────────

    from notifications.telegram_notifier import notify_trade_executed, notify_trade_closed, notify_bot_started
    
    def on_trade_executed(env: MessageEnvelope):
        cmd = env.payload
        notify_trade_executed(
            symbol=cmd.symbol,
            direction=cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction),
            lot=float(cmd.quantity),
            entry=float(cmd.execution_price),
            sl=0.0,
            tp=0.0,
            ticket="GQOS",
            probability=0.0
        )
        
    last_closed_dir   = {}
    last_closed_price = {}   # ← เก็บ exit_price สำหรับ Learning Loop

    def on_position_closed(env: MessageEnvelope):
        cmd = env.payload
        last_closed_dir[cmd.symbol] = (
            cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction)
        )
        # ─── Learning Loop: เก็บ exit_price ──────────────────────────
        if hasattr(cmd, 'exit_price'):
            last_closed_price[cmd.symbol] = float(cmd.exit_price)
        # ─────────────────────────────────────────────────────────────
        
    def on_realized_pnl(env: MessageEnvelope):
        cmd       = env.payload
        acc       = mt5.account_info()
        balance   = acc.balance if acc else 0.0
        direction = last_closed_dir.get(cmd.symbol, "UNKNOWN")

        notify_trade_closed(
            ticket="UNKNOWN",
            symbol=cmd.symbol,
            direction=direction,
            profit=float(cmd.realized_pnl),
            rr=0.0,
            balance=float(balance)
        )

        # ─── Learning Loop: บันทึก outcome ───────────────────────────
        try:
            exit_price = last_closed_price.get(cmd.symbol, 0.0)
            record = outcome_logger.on_trade_closed(
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
        
    from gqos.risk.events import TradeExecutedEvent
    from gqos.accounting.events import PositionClosedEvent, RealizedPnLEmittedEvent
    
    evt_bus.subscribe(TradeExecutedEvent,     on_trade_executed)
    evt_bus.subscribe(PositionClosedEvent,    on_position_closed)
    evt_bus.subscribe(RealizedPnLEmittedEvent, on_realized_pnl)
    
    notify_bot_started()
    live_engine.start()
    
    logger.info("GQOS Live Engine is completely booted and running. Press Ctrl+C to exit.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down GQOS...")
        alpha_worker.stop()
        live_engine.stop()
        mt5.shutdown()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    main()
