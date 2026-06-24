import time
from decimal import Decimal
from gqos.messaging.bus import LocalEventBus, LocalCommandBus
from gqos.messaging.store import InMemoryEventStore
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import (
    ExecuteTradeCommand, TradeExecutedEvent, TradeRejectedByExposureLimit,
    RiskBudgetAllocated
)
from gqos.risk.models import RiskBudget
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.decorator import RiskGuardedCommandBus

def run_replay():
    print("=== M7C Exposure Engine Replay ===\n")
    
    logger = type("DummyLogger", (), {"log": lambda self, lvl, msg: print(f"[{lvl}] {msg}")})()
    
    event_store = InMemoryEventStore()
    event_bus = LocalEventBus(logger, event_store=event_store)
    inner_cmd_bus = LocalCommandBus(logger)
    
    # 1. Setup Risk Budget & Circuit Breaker
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_m7c", total_capacity=Decimal('10000.0'), utilized_capacity=Decimal('0.0')))
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    
    # 2. Setup Assets & Exposure Engine
    directory = AssetDirectory()
    directory.register_asset(AssetMetadata("AAPL", "Tech", "Equity", "Mega-Cap"))
    directory.register_asset(AssetMetadata("MSFT", "Tech", "Equity", "Mega-Cap"))
    directory.register_asset(AssetMetadata("JPM", "Financials", "Equity", "Value"))
    
    limits = ExposureLimits(
        max_gross_exposure=Decimal('5000.0'),
        max_net_exposure=Decimal('3000.0'),
        max_symbol_exposure=Decimal('1000.0'),
        max_sector_exposure=Decimal('1500.0'),
        max_correlation_group_exposure=Decimal('2000.0')
    )
    
    exposure_engine = ExposureEngine(directory, limits)
    
    # 3. Setup Bus
    guarded_bus = RiskGuardedCommandBus(inner_cmd_bus, event_bus, engine, cb_engine, exposure_engine)
    
    # Plugin mock
    def dummy_executor(env: MessageEnvelope[ExecuteTradeCommand]):
        cmd = env.payload
        print(f"  -> Plugin Executing Trade: {cmd.symbol} for ${cmd.estimated_value}")
        # Simulate successful execution
        price = cmd.estimated_value / abs(cmd.quantity)
        evt = TradeExecutedEvent(cmd.strategy_id, cmd.symbol, cmd.quantity, price)
        # Apply to exposure engine manually since it listens to TradeExecutedEvent
        exposure_engine.apply_trade(evt)
        event_bus.publish(MessageEnvelope.create(evt, version=1, correlation_id=env.correlation_id))
        
    inner_cmd_bus.register_handler(ExecuteTradeCommand, dummy_executor)
    
    # Subscriptions for logging
    event_bus.subscribe(TradeRejectedByExposureLimit, lambda e: print(f"  -> [EXPOSURE BLOCK] {e.payload.reason}"))
    
    print("--- Trade 1: AAPL Long $1,000 (Tech Sector) ---")
    guarded_bus.dispatch(MessageEnvelope.create(ExecuteTradeCommand("AAPL", Decimal('10'), Decimal('1000.0'), "strat_m7c"), version=1, correlation_id="t1"))
    
    print("\n--- Trade 2: JPM Long $1,000 (Financials Sector) ---")
    guarded_bus.dispatch(MessageEnvelope.create(ExecuteTradeCommand("JPM", Decimal('10'), Decimal('1000.0'), "strat_m7c"), version=1, correlation_id="t2"))
    
    print("\n--- Trade 3: MSFT Long $1,000 (Tech Sector) ---")
    print("  -> Should fail because Tech Sector limit is 1,500, and we already have 1,000 AAPL.")
    guarded_bus.dispatch(MessageEnvelope.create(ExecuteTradeCommand("MSFT", Decimal('10'), Decimal('1000.0'), "strat_m7c"), version=1, correlation_id="t3"))
    
    print("\n--- Trade 4: MSFT Long $400 (Tech Sector) ---")
    print("  -> Should pass because 1000 + 400 = 1400 (under 1,500 Tech limit).")
    guarded_bus.dispatch(MessageEnvelope.create(ExecuteTradeCommand("MSFT", Decimal('4'), Decimal('400.0'), "strat_m7c"), version=1, correlation_id="t4"))
    
    print("\n=== Final Exposure State ===")
    print(f"Gross: {exposure_engine._state.gross_exposure}")
    print(f"Net: {exposure_engine._state.net_exposure}")
    print(f"Tech Sector: {exposure_engine._state.get_sector_gross('Tech')}")
    print(f"Financials Sector: {exposure_engine._state.get_sector_gross('Financials')}")

if __name__ == "__main__":
    run_replay()
