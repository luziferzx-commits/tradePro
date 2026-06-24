import os
import sys
import logging
import time
from decimal import Decimal

# Add root directory to path
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

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("GQOS-Live")

class DefaultFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        # Rough MT5 comm/spread model
        # Just returning 0 for now as MT5 deducts it from balance automatically.
        return Decimal('0'), "USD"

class DefaultFxConverter:
    def convert(self, amount, from_curr, to_curr):
        # 1:1 for now
        return amount

def main():
    logger.info("=========================================")
    logger.info("  GQOS LIVE ENGINE (INSTITUTIONAL MODE)  ")
    logger.info("=========================================")
    
    # 1. Connect MT5
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        return
        
    acc_info = mt5.account_info()
    if not acc_info:
        logger.error("Could not retrieve MT5 account info.")
        return
        
    initial_capital = Decimal(str(acc_info.balance))
    logger.info(f"Connected to MT5. Initial Capital: ${initial_capital}")

    # 2. Setup Bus
    cmd_bus = LocalCommandBus(logger)
    evt_bus = LocalEventBus(logger)
    
    # 3. Setup Accounting & Portfolio
    accounting = AccountingEngine(evt_bus, DefaultFeeModel(), DefaultFxConverter())
    portfolio = PortfolioManager("LivePort", initial_capital)
    portfolio.allocate_capital("gqos_alpha_v1", initial_capital)
    
    # 4. Setup Execution & Live Adapters
    oms = OrderManagementSystem(evt_bus)
    
    def oms_callback(order_id, status, fill_qty, fill_price, msg):
        if status == "FILL":
            oms.apply_fill(order_id, fill_qty, fill_price)
        else:
            oms.update_order_status(order_id, OrderStatus(status), msg)
            
    adapter = MT5BrokerAdapter(evt_bus, oms_callback)
    safety = GlobalKillSwitch(oms, adapter)
    hb_monitor = HeartbeatMonitor(evt_bus, safety, timeout_seconds=5.0)
    
    snapshot_path = "gqos_ledger_state.json"
    persistence = LedgerSnapshotService(snapshot_path)
    
    live_engine = LiveTradingEngine(evt_bus, oms, adapter, safety, persistence, accounting, portfolio)
    
    # 5. Setup Risk Engines
    sizing_engine = PositionSizingEngine()
    policy = FixedFractionalPolicy(fraction=Decimal('0.02')) # 2% risk
    
    cb_engine = CircuitBreakerEngine()
    
    asset_dir = AssetDirectory()
    # Register symbols (mock metadata)
    for sym in ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "US500", "EURUSD", "GBPUSD", "USDJPY", "NAS100", "GER40"]:
        asset_dir.register_asset(AssetMetadata(sym, "MIXED", "FX", sym))
        
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
    
    # NEW: News Filter
    from gqos.risk.news_filter import NewsFilter
    from gqos.risk.news_stage import NewsGuardStage
    news_filter = NewsFilter(block_minutes=15)
    news_stage = NewsGuardStage(news_filter)

    # 6. Setup Trading Pipeline
    stages = [
        news_stage,
        SizingStage(sizing_engine, policy),
        CircuitBreakerStage(cb_engine),
        ExposureStage(exposure),
        RiskBudgetStage(risk_engine),
        PortfolioSnapshotStage(portfolio),
        PortfolioReservationStage(portfolio),
        ExecutionStage(cmd_bus, portfolio)
    ]
    pipeline = TradingPipeline(stages, evt_bus)
    
    # Register the command handler so AlphaWorker's SizePositionCommand enters the pipeline
    def handle_sizing_command(env: MessageEnvelope):
        pipeline.execute(env)
        
    cmd_bus.register_handler(SizePositionCommand, handle_sizing_command)
    # The AlphaWorker publishes directly to cmd_bus or evt_bus? 
    # AlphaWorker currently uses _event_bus.publish. Let's make it use cmd_bus!
    
    # 7. Start Alpha Worker
    alpha_worker = AlphaWorker(cmd_bus) 
    
    # Let AlphaWorker start
    alpha_worker.start()
    
    # 7. Setup Notifications
    from notifications.telegram_notifier import notify_trade_executed, notify_trade_closed, notify_bot_started
    
    def on_trade_executed(env: MessageEnvelope):
        cmd = env.payload
        # Convert TradeExecutedEvent back to Telegram format
        notify_trade_executed(
            symbol=cmd.symbol,
            direction=cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction),
            lot=float(cmd.quantity),
            entry=float(cmd.execution_price),
            sl=0.0, # SL/TP handled by strategy later
            tp=0.0,
            ticket=cmd.order_id,
            probability=0.0 # Will be populated if AlphaWorker injects metadata
        )
        
    def on_position_closed(env: MessageEnvelope):
        cmd = env.payload
        # Calculate approximate profit from event (if available) or zero
        notify_trade_closed(
            ticket="UNKNOWN",
            symbol=cmd.symbol,
            direction=cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction),
            profit=0.0, # Profit is in RealizedPnLEmittedEvent
            rr=0.0
        )
        
    from gqos.risk.events import TradeExecutedEvent
    from gqos.accounting.events import PositionClosedEvent
    
    evt_bus.subscribe(TradeExecutedEvent, on_trade_executed)
    evt_bus.subscribe(PositionClosedEvent, on_position_closed)
    
    # Notify boot
    notify_bot_started()

    # 8. Start Everything
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
