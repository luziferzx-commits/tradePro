from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.messaging.contracts import MessageEnvelope
from gqos.messaging.bus import IEventBus
from gqos.risk.events import TradeExecutedEvent
from gqos.accounting.engine import AccountingEngine
from gqos.accounting.fee_model import MockFeeModel
from gqos.accounting.fx import MockFxConverter
from gqos.accounting.events import RealizedPnLEmittedEvent
from gqos.portfolio.manager import PortfolioManager

class MockEventBus(IEventBus):
    def __init__(self):
        self.published_events = []
        self.subscribers = {}
        
    def publish(self, envelope: MessageEnvelope) -> None:
        self.published_events.append(envelope.payload)
        event_type = type(envelope.payload)
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                handler(envelope)
                
    def subscribe(self, event_type, handler) -> None:
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        
    def unsubscribe(self, event_type, handler) -> None:
        pass

def test_portfolio_manager_updates_from_pnl():
    bus = MockEventBus()
    engine = AccountingEngine(bus, MockFeeModel(Decimal('0')), MockFxConverter())
    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('50000.0'))
    
    def on_pnl_emitted(envelope):
        manager.apply_realized_pnl(envelope.payload.strategy_id, envelope.payload.realized_pnl)
        
    bus.subscribe(RealizedPnLEmittedEvent, on_pnl_emitted)
    
    # Open Long 100 @ 100
    bus.publish(MessageEnvelope.create(TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')), version=1, correlation_id="1"))
    
    # Close Long 100 @ 150 -> PnL 5000
    bus.publish(MessageEnvelope.create(TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('100.0'), Decimal('150.0')), version=1, correlation_id="2"))
    
    alloc = manager.state.allocations["s1"]
    assert alloc.allocated_capital == Decimal('55000.0')
    assert manager.state.total_equity == Decimal('105000.0')

if __name__ == "__main__":
    test_portfolio_manager_updates_from_pnl()
    print("M10A test_portfolio_sync passed!")
