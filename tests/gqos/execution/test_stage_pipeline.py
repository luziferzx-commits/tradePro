from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.sizing.events import SizePositionCommand, PositionSizedEvent, SizingFailedEvent
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.policies import FixedFractionalPolicy
from gqos.sizing.portfolio import PortfolioSnapshot

from gqos.risk.circuit_breaker import CircuitBreaker
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.engine import RiskBudgetEngine
from gqos.risk.store import RiskBudgetStore
from gqos.risk.assets import AssetDirectory
from gqos.risk.events import ExecuteTradeCommand

from gqos.execution.pipeline import TradingPipeline
from gqos.execution.stages import SizingStage, CircuitBreakerStage, ExposureStage, RiskBudgetStage, PortfolioSnapshotStage, PortfolioReservationStage, ExecutionStage
from gqos.portfolio.manager import PortfolioManager

class MockCommandBus(ICommandBus):
    def __init__(self):
        self.dispatched_commands = []
    def dispatch(self, envelope: MessageEnvelope[Command]):
        self.dispatched_commands.append(envelope.payload)
        return "FORWARDED"
    def register_handler(self, command_type, handler) -> None:
        pass

class MockEventBus(IEventBus):
    def __init__(self):
        self.published_events = []
    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        self.published_events.append(envelope.payload)
    def subscribe(self, event_type, handler) -> None:
        pass
    def unsubscribe(self, event_type, handler) -> None:
        pass

def setup_pipeline():
    # Setup Engine components
    engine = PositionSizingEngine()
    policy = FixedFractionalPolicy(fraction=Decimal('0.05'))
    
    # Portfolio
    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('100000.0'))
    
    from gqos.risk.engine import CircuitBreakerEngine
    cb = CircuitBreakerEngine()
    asset_dir = AssetDirectory()
    from gqos.risk.assets import AssetMetadata
    asset_dir.register_asset(AssetMetadata("AAPL", "Tech", "EQUITY", "Tech-MegaCaps"))
    from gqos.risk.exposure import ExposureLimits
    exposure = ExposureEngine(asset_dir, ExposureLimits(max_gross_exposure=Decimal('1000000.0'), max_net_exposure=Decimal('1000000.0'), max_symbol_exposure=Decimal('1000000.0'), max_sector_exposure=Decimal('1000000.0'), max_correlation_group_exposure=Decimal('1000000.0')))
    store = RiskBudgetStore()
    from gqos.risk.models import RiskBudget
    store.save(RiskBudget("s1", Decimal('10000.0'), Decimal('0')))
    budget = RiskBudgetEngine(store)
    
    event_bus = MockEventBus()
    execution_bus = MockCommandBus()
    
    # Create Pipeline
    stages = [
        PortfolioSnapshotStage(manager),
        SizingStage(engine, policy),
        CircuitBreakerStage(cb),
        ExposureStage(exposure),
        RiskBudgetStage(budget),
        PortfolioReservationStage(manager),
        ExecutionStage(execution_bus, manager)
    ]
    
    pipeline = TradingPipeline(stages, event_bus)
    return pipeline, event_bus, execution_bus, store, cb, manager

def test_stage_pipeline_success():
    pipeline, event_bus, exec_bus, store, cb, manager = setup_pipeline()
    
    cmd = SizePositionCommand("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'))
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c1")
    
    res = pipeline.dispatch(env)
    
    assert res == "Completed pipeline execution."
    assert len(exec_bus.dispatched_commands) == 1
    assert isinstance(exec_bus.dispatched_commands[0], ExecuteTradeCommand)
    
    # Check events (PositionSizedEvent, RiskBudgetAllocated)
    event_types = [type(e).__name__ for e in event_bus.published_events]
    assert "PositionSizedEvent" in event_types
    assert "RiskBudgetAllocated" in event_types

def test_stage_pipeline_halt_on_circuit_breaker():
    pipeline, event_bus, exec_bus, store, cb, manager = setup_pipeline()
    
    # Trip CB
    cb.trip("s1", "Test")
    
    cmd = SizePositionCommand("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'))
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c2")
    
    res = pipeline.dispatch(env)
    
    assert "Halted at CircuitBreakerStage" in res
    assert len(exec_bus.dispatched_commands) == 0
    
    # Should still size before CB blocks
    event_types = [type(e).__name__ for e in event_bus.published_events]
    assert "PositionSizedEvent" in event_types
    assert "TradeRejectedByCircuitBreaker" in event_types
    assert "RiskBudgetAllocated" not in event_types

if __name__ == "__main__":
    test_stage_pipeline_success()
    test_stage_pipeline_halt_on_circuit_breaker()
    print("Stage Pipeline tests passed!")
