from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.sizing.events import SizePositionCommand, PositionSizedEvent
from gqos.sizing.pipeline import PositionSizingPipeline
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.policies import FixedFractionalPolicy
from gqos.sizing.models import RoundingPolicy
from gqos.sizing.portfolio import PortfolioSnapshot
from gqos.risk.events import ExecuteTradeCommand

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

def test_sizing_pipeline():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    engine = PositionSizingEngine()
    policy = FixedFractionalPolicy(fraction=Decimal('0.05')) # 5%
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))

    pipeline = PositionSizingPipeline(inner_bus, event_bus, engine, policy, portfolio)
    
    # Send a SizePositionCommand (Price = 100) -> Target Qty = 50
    cmd = SizePositionCommand("strat_1", "AAPL", TradeDirection.BUY, Decimal('100.0'))
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c1")
    
    res = pipeline.dispatch(env)
    
    assert res == "FORWARDED"
    
    # Should have published PositionSizedEvent
    assert len(event_bus.published_events) == 1
    sized_evt = event_bus.published_events[0]
    assert isinstance(sized_evt, PositionSizedEvent)
    assert sized_evt.result.quantity == Decimal('50')
    
    # Should have forwarded ExecuteTradeCommand
    assert len(inner_bus.dispatched_commands) == 1
    exec_cmd = inner_bus.dispatched_commands[0]
    assert isinstance(exec_cmd, ExecuteTradeCommand)
    assert exec_cmd.quantity == Decimal('50')
    assert exec_cmd.estimated_value == Decimal('5000.0')

if __name__ == "__main__":
    test_sizing_pipeline()
    print("Sizing Pipeline test passed!")
