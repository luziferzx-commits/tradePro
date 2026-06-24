from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.messaging.contracts import MessageEnvelope
from gqos.messaging.bus import IEventBus
from gqos.risk.events import TradeExecutedEvent
from gqos.accounting.engine import AccountingEngine
from gqos.accounting.fee_model import MockFeeModel
from gqos.accounting.fx import MockFxConverter
from gqos.accounting.events import (
    PositionOpenedEvent, PositionAdjustedEvent, PositionClosedEvent,
    RealizedPnLEmittedEvent, FeeChargedEvent
)

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

def test_long_open_partial_close_full_close():
    bus = MockEventBus()
    fee_model = MockFeeModel(commission_per_share=Decimal('0.01'))
    fx = MockFxConverter()
    engine = AccountingEngine(bus, fee_model, fx)
    
    # 1. Open Long 100 @ 150
    trade1 = TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('150.0'))
    bus.publish(MessageEnvelope.create(trade1, version=1, correlation_id="c1"))
    
    pos = engine.state.positions["s1_AAPL"]
    assert pos.quantity == Decimal('100.0')
    assert pos.average_price == Decimal('150.0')
    assert pos.direction == TradeDirection.BUY
    
    events_type = [type(e) for e in bus.published_events]
    assert PositionOpenedEvent in events_type
    
    # 2. Partial Close 40 @ 160
    trade2 = TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('40.0'), Decimal('160.0'))
    bus.publish(MessageEnvelope.create(trade2, version=1, correlation_id="c2"))
    
    pos = engine.state.positions["s1_AAPL"]
    assert pos.quantity == Decimal('60.0')
    assert pos.average_price == Decimal('150.0') # Avg price doesn't change on partial close
    
    pnl_events = [e for e in bus.published_events if isinstance(e, RealizedPnLEmittedEvent)]
    assert len(pnl_events) == 1
    # PnL = (160 - 150) * 40 = 400
    assert pnl_events[0].realized_pnl == Decimal('400.0')
    
    # 3. Full Close 60 @ 145
    trade3 = TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('60.0'), Decimal('145.0'))
    bus.publish(MessageEnvelope.create(trade3, version=1, correlation_id="c3"))
    
    assert "s1_AAPL" not in engine.state.positions
    pnl_events = [e for e in bus.published_events if isinstance(e, RealizedPnLEmittedEvent)]
    assert len(pnl_events) == 2
    # PnL = (145 - 150) * 60 = -300
    assert pnl_events[1].realized_pnl == Decimal('-300.0')

def test_short_open_partial_close_full_close():
    bus = MockEventBus()
    fee_model = MockFeeModel(commission_per_share=Decimal('0.00'))
    fx = MockFxConverter()
    engine = AccountingEngine(bus, fee_model, fx)
    
    # Open Short 100 @ 150
    trade1 = TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('100.0'), Decimal('150.0'))
    bus.publish(MessageEnvelope.create(trade1, version=1, correlation_id="c1"))
    
    # Partial Close 40 @ 140 (Buy to cover)
    trade2 = TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('40.0'), Decimal('140.0'))
    bus.publish(MessageEnvelope.create(trade2, version=1, correlation_id="c2"))
    
    pnl_events = [e for e in bus.published_events if isinstance(e, RealizedPnLEmittedEvent)]
    assert len(pnl_events) == 1
    # PnL = (Entry - Exit) * Qty = (150 - 140) * 40 = 400
    assert pnl_events[0].realized_pnl == Decimal('400.0')
    
    # Full Close 60 @ 160 (Buy to cover)
    trade3 = TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('60.0'), Decimal('160.0'))
    bus.publish(MessageEnvelope.create(trade3, version=1, correlation_id="c3"))
    
    pnl_events = [e for e in bus.published_events if isinstance(e, RealizedPnLEmittedEvent)]
    assert len(pnl_events) == 2
    # PnL = (150 - 160) * 60 = -600
    assert pnl_events[1].realized_pnl == Decimal('-600.0')

def test_long_to_short_flip():
    bus = MockEventBus()
    engine = AccountingEngine(bus, MockFeeModel(Decimal('0')), MockFxConverter())
    
    # Open Long 100 @ 100
    bus.publish(MessageEnvelope.create(TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')), version=1, correlation_id="1"))
    
    # Flip Short 150 @ 120 (Close 100 Long, Open 50 Short)
    bus.publish(MessageEnvelope.create(TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('150.0'), Decimal('120.0')), version=1, correlation_id="2"))
    
    pnl_events = [e for e in bus.published_events if isinstance(e, RealizedPnLEmittedEvent)]
    assert len(pnl_events) == 1
    assert pnl_events[0].realized_pnl == Decimal('2000.0') # (120-100)*100
    
    pos = engine.state.positions["s1_AAPL"]
    assert pos.quantity == Decimal('50.0')
    assert pos.average_price == Decimal('120.0')
    assert pos.direction == TradeDirection.SELL

def test_short_to_long_flip():
    bus = MockEventBus()
    engine = AccountingEngine(bus, MockFeeModel(Decimal('0')), MockFxConverter())
    
    # Open Short 100 @ 100
    bus.publish(MessageEnvelope.create(TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('100.0'), Decimal('100.0')), version=1, correlation_id="1"))
    
    # Flip Long 150 @ 90 (Close 100 Short, Open 50 Long)
    bus.publish(MessageEnvelope.create(TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('150.0'), Decimal('90.0')), version=1, correlation_id="2"))
    
    pnl_events = [e for e in bus.published_events if isinstance(e, RealizedPnLEmittedEvent)]
    assert len(pnl_events) == 1
    assert pnl_events[0].realized_pnl == Decimal('1000.0') # (100-90)*100
    
    pos = engine.state.positions["s1_AAPL"]
    assert pos.quantity == Decimal('50.0')
    assert pos.average_price == Decimal('90.0')
    assert pos.direction == TradeDirection.BUY

def test_fee_charged_and_deducted():
    bus = MockEventBus()
    fee_model = MockFeeModel(commission_per_share=Decimal('0.05'))
    engine = AccountingEngine(bus, fee_model, MockFxConverter())
    
    # Open Long 100 @ 100
    bus.publish(MessageEnvelope.create(TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')), version=1, correlation_id="1"))
    
    fee_events = [e for e in bus.published_events if isinstance(e, FeeChargedEvent)]
    assert len(fee_events) == 1
    assert fee_events[0].amount == Decimal('5.0') # 100 * 0.05
    
    cash = engine.state.cash["s1_USD"]
    assert cash.balance == Decimal('-5.0')

def test_rebuild_state_from_event_stream():
    bus = MockEventBus()
    engine = AccountingEngine(bus, MockFeeModel(Decimal('0')), MockFxConverter())
    
    # Rebuild from events, we don't dispatch TradeExecuted, we dispatch the pure state events
    events = [
        PositionOpenedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')),
        FeeChargedEvent("s1", Decimal('1.0'), "USD", "Commission"),
        PositionAdjustedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('50.0'), Decimal('100.0'), Decimal('-50.0'))
    ]
    
    engine2 = AccountingEngine(MockEventBus(), MockFeeModel(Decimal('0')), MockFxConverter())
    for e in events:
        engine2.apply_event(e)
        
    assert engine2.state.positions["s1_AAPL"].quantity == Decimal('50.0')
    assert engine2.state.cash["s1_USD"].balance == Decimal('-1.0')

if __name__ == "__main__":
    test_long_open_partial_close_full_close()
    test_short_open_partial_close_full_close()
    test_long_to_short_flip()
    test_short_to_long_flip()
    test_fee_charged_and_deducted()
    test_rebuild_state_from_event_stream()
    print("M10A test_accounting_engine passed!")
