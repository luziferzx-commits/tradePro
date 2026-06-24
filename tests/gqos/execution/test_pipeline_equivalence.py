from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.sizing.events import SizePositionCommand, PositionSizedEvent
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.policies import FixedFractionalPolicy
from gqos.sizing.portfolio import PortfolioSnapshot

from gqos.risk.circuit_breaker import CircuitBreaker
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.exposure import ExposureLimits
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.store import RiskBudgetStore
from gqos.risk.models import RiskBudget
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.events import ExecuteTradeCommand

# Old pipeline components
from gqos.sizing.pipeline import PositionSizingPipeline
from gqos.risk.decorator import RiskGuardedCommandBus

# New pipeline components
from gqos.execution.pipeline import TradingPipeline
from gqos.execution.stages import SizingStage, CircuitBreakerStage, ExposureStage, RiskBudgetStage

class MockEventBus(IEventBus):
    def __init__(self):
        self.published_events = []
    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        self.published_events.append(envelope.payload)
    def subscribe(self, event_type, handler) -> None:
        pass
    def unsubscribe(self, event_type, handler) -> None:
        pass

class MockCommandBus(ICommandBus):
    def __init__(self):
        self.dispatched_commands = []
    def dispatch(self, envelope: MessageEnvelope[Command]):
        self.dispatched_commands.append(envelope.payload)
        return "EXECUTED"
    def register_handler(self, command_type, handler) -> None:
        pass

def create_shared_infrastructure():
    asset_dir = AssetDirectory()
    asset_dir.register_asset(AssetMetadata("AAPL", "Tech", "EQUITY", "Tech-MegaCaps"))
    
    cb_engine = CircuitBreakerEngine()
    exposure_engine = ExposureEngine(asset_dir, ExposureLimits(max_gross_exposure=Decimal('1000000.0'), max_net_exposure=Decimal('1000000.0'), max_symbol_exposure=Decimal('1000000.0'), max_sector_exposure=Decimal('1000000.0'), max_correlation_group_exposure=Decimal('1000000.0')))
    
    store = RiskBudgetStore()
    store.save(RiskBudget("s1", Decimal('50000.0'), Decimal('0')))
    budget_engine = RiskBudgetEngine(store)
    
    sizing_engine = PositionSizingEngine()
    policy = FixedFractionalPolicy(fraction=Decimal('0.1')) # 10%
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0')) # 10k trade
    
    return asset_dir, cb_engine, exposure_engine, budget_engine, sizing_engine, policy, portfolio

def test_pipeline_equivalence():
    cmd = SizePositionCommand("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'))
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c1")
    
    # --- OLD PIPELINE ---
    a, cb_old, exp_old, bud_old, size_engine_old, pol_old, port_old = create_shared_infrastructure()
    event_bus_old = MockEventBus()
    exec_bus_old = MockCommandBus()
    
    risk_bus = RiskGuardedCommandBus(inner=exec_bus_old, event_bus=event_bus_old, engine=bud_old, cb_engine=cb_old, exposure_engine=exp_old)
    old_pipeline = PositionSizingPipeline(risk_bus, event_bus_old, size_engine_old, pol_old, port_old)
    
    old_pipeline.dispatch(env)
    
    # --- NEW PIPELINE ---
    a, cb_new, exp_new, bud_new, size_engine_new, pol_new, port_new = create_shared_infrastructure()
    from gqos.execution.stages import SizingStage, CircuitBreakerStage, ExposureStage, RiskBudgetStage, PortfolioSnapshotStage, PortfolioReservationStage, ExecutionStage
    from gqos.portfolio.manager import PortfolioManager
    
    event_bus_new = MockEventBus()
    exec_bus_new = MockCommandBus()
    
    manager_new = PortfolioManager("p1", Decimal('100000.0'))
    manager_new.allocate_capital("s1", Decimal('100000.0'))
    
    stages = [
        PortfolioSnapshotStage(manager_new),
        SizingStage(size_engine_new, pol_new),
        CircuitBreakerStage(cb_new),
        ExposureStage(exp_new),
        RiskBudgetStage(bud_new),
        PortfolioReservationStage(manager_new),
        ExecutionStage(exec_bus_new, manager_new)
    ]
    
    new_pipeline = TradingPipeline(stages, event_bus_new)
    
    new_pipeline.dispatch(env)
    
    # --- VERIFICATION ---
    # Both should execute 1 trade
    assert len(exec_bus_old.dispatched_commands) == 1
    assert len(exec_bus_new.dispatched_commands) == 1
    
    # Command values should match
    cmd_old = exec_bus_old.dispatched_commands[0]
    cmd_new = exec_bus_new.dispatched_commands[0]
    assert cmd_old.quantity == cmd_new.quantity
    assert cmd_old.estimated_value == cmd_new.estimated_value
    
    # Both should emit Sized and Allocated events
    types_old = [type(e).__name__ for e in event_bus_old.published_events]
    types_new = [type(e).__name__ for e in event_bus_new.published_events]
    
    assert "PositionSizedEvent" in types_old
    assert "PositionSizedEvent" in types_new
    assert "RiskBudgetAllocated" in types_old
    assert "RiskBudgetAllocated" in types_new

if __name__ == "__main__":
    test_pipeline_equivalence()
    print("Pipeline Equivalence test passed!")
