from decimal import Decimal
from types import SimpleNamespace
from gqos.common.enums import TradeDirection
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.portfolio.manager import PortfolioManager
from gqos.portfolio.events import CashReservedEvent, CashReleasedEvent, TradeRejectedByPortfolioEvent
from gqos.sizing.events import SizePositionCommand
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.policies import FixedFractionalPolicy
from gqos.risk.engine import CircuitBreakerEngine, RiskBudgetEngine
from gqos.risk.store import RiskBudgetStore
from gqos.risk.models import RiskBudget
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits
from gqos.execution.pipeline import TradingPipeline
from gqos.execution.stages import SizingStage, CircuitBreakerStage, ExposureStage, RiskBudgetStage, PortfolioSnapshotStage, PortfolioReservationStage, ExecutionStage

class MockFailingCommandBus(ICommandBus):
    def dispatch(self, envelope: MessageEnvelope[Command]):
        raise RuntimeError("Execution failed synchronously")
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

def setup_m9c_pipeline(failing_execution=False):
    from gqos.execution import stages as execution_stages
    execution_stages.mt5.positions_get = lambda: []
    execution_stages.mt5.account_info = lambda: SimpleNamespace(balance=100000.0)
    execution_stages.mt5.symbol_info_tick = lambda symbol: SimpleNamespace(ask=100.0, bid=100.0)
    try:
        from data.mt5_client import mt5_client
        mt5_client.resolve_symbol = lambda symbol: symbol
    except Exception:
        pass

    engine = PositionSizingEngine()
    policy = FixedFractionalPolicy(fraction=Decimal('0.10'))
    
    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('50000.0'))
    
    cb = CircuitBreakerEngine()
    asset_dir = AssetDirectory()
    asset_dir.register_asset(AssetMetadata("AAPL", "Tech", "EQUITY", "Tech-MegaCaps"))
    exposure = ExposureEngine(asset_dir, ExposureLimits(max_gross_exposure=Decimal('1000000.0'), max_net_exposure=Decimal('1000000.0'), max_symbol_exposure=Decimal('1000000.0'), max_sector_exposure=Decimal('1000000.0'), max_correlation_group_exposure=Decimal('1000000.0')))
    
    store = RiskBudgetStore()
    store.save(RiskBudget("s1", Decimal('500000.0'), Decimal('0')))
    budget = RiskBudgetEngine(store)
    
    event_bus = MockEventBus()
    
    if failing_execution:
        execution_bus = MockFailingCommandBus()
    else:
        from tests.gqos.execution.test_stage_pipeline import MockCommandBus
        execution_bus = MockCommandBus()
        
    stages = [
        PortfolioSnapshotStage(manager),
        SizingStage(engine, policy),
        CircuitBreakerStage(cb),
        ExposureStage(exposure, max_portfolio_risk_pct=1.0),
        RiskBudgetStage(budget),
        PortfolioReservationStage(manager),
        ExecutionStage(execution_bus, manager)
    ]
    
    pipeline = TradingPipeline(stages, event_bus)
    return pipeline, event_bus, manager

def test_successful_reservation():
    pipeline, event_bus, manager = setup_m9c_pipeline()
    
    # Capital is 50,000, Risk is 10%, Risk Amount is 5,000.
    # Entry price 100, Stop 90, Loss per share 10.
    # Quantity = 5,000 / 10 = 500.
    # Estimated Value = 500 * 100 = 50,000.
    cmd = SizePositionCommand("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('90.0'))
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c1")
    
    pipeline.dispatch(env)
    
    # Check that cash was reserved
    alloc = manager.state.allocations["s1"]
    assert alloc.reserved_cash == Decimal('5000.0')
    assert alloc.buying_power == Decimal('45000.0')
    
    # Check event
    event_types = [type(e).__name__ for e in event_bus.published_events]
    assert "CashReservedEvent" in event_types

def test_over_reservation_rejected():
    pipeline, event_bus, manager = setup_m9c_pipeline()
    
    # Capital is 50,000, fraction = 0.50 -> Risk amount 25,000.
    # Quantity = 25,000 / 10 = 2,500.
    # Estimated Value = 250,000 > 50,000 Buying Power!
    
    # Let's bypass sizing to inject a large trade
    from gqos.risk.events import ExecuteTradeCommand
    cmd = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('2500'), Decimal('250000.0'), "s1")
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c2")
    
    res = pipeline.dispatch(env)
    print(f"Res: {res}")
    assert "Portfolio Reservation Failed" in res
    
    # Verify no cash reserved
    alloc = manager.state.allocations["s1"]
    assert alloc.reserved_cash == Decimal('0.0')
    
    # Verify event
    event_types = [type(e).__name__ for e in event_bus.published_events]
    assert "TradeRejectedByPortfolioEvent" in event_types

def test_execution_failure_releases_cash():
    pipeline, event_bus, manager = setup_m9c_pipeline(failing_execution=True)
    
    cmd = SizePositionCommand("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('90.0'))
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c3")
    
    res = pipeline.dispatch(env)
    assert "Execution Failed" in res
    
    # Cash should be released
    alloc = manager.state.allocations["s1"]
    assert alloc.reserved_cash == Decimal('0.0')
    assert alloc.buying_power == Decimal('50000.0')
    
    # Check event
    event_types = [type(e).__name__ for e in event_bus.published_events]
    assert "CashReservedEvent" in event_types
    assert "CashReleasedEvent" in event_types

def test_portfolio_reservation_stage_releases_cash_on_close():
    from gqos.execution.pipeline import PipelineContext
    from gqos.risk.events import ExecuteTradeCommand

    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('50000.0'))
    stage = PortfolioReservationStage(manager)
    cmd = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('50'), Decimal('5000.0'), "s1")
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c4")

    result = stage.process(env, PipelineContext())
    assert result.continue_pipeline is True

    alloc = manager.state.allocations["s1"]
    assert alloc.reserved_cash == Decimal('5000.0')

    released = stage.release_for_symbol("AAPL")
    assert released is True
    assert alloc.reserved_cash == Decimal('0.0')
    assert alloc.buying_power == Decimal('50000.0')

def test_portfolio_reservation_stage_release_event_for_allocation():
    from gqos.execution.pipeline import PipelineContext
    from gqos.risk.events import ExecuteTradeCommand

    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('50000.0'))
    stage = PortfolioReservationStage(manager)
    cmd = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('50'), Decimal('5000.0'), "s1")
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c5")

    result = stage.process(env, PipelineContext())
    allocation_id = result.envelope.payload.portfolio_allocation_id

    release_event = stage.release_event_for_allocation_id(allocation_id, "Order Rejected Without Fill")
    assert release_event is not None
    assert release_event.allocation_id == allocation_id
    assert release_event.amount == Decimal('5000.0')
    assert release_event.new_reserved_cash == Decimal('0.0')
    assert release_event.new_buying_power == Decimal('50000.0')

if __name__ == "__main__":
    test_successful_reservation()
    test_over_reservation_rejected()
    test_execution_failure_releases_cash()
    test_portfolio_reservation_stage_releases_cash_on_close()
    test_portfolio_reservation_stage_release_event_for_allocation()
    print("M9C Portfolio Allocation tests passed!")
