from decimal import Decimal
from datetime import datetime, timedelta
from gqos.messaging.contracts import MessageEnvelope
from gqos.common.enums import TradeDirection
from gqos.accounting.events import RealizedPnLEmittedEvent, FeeChargedEvent
from gqos.risk.events import TradeExecutedEvent
from gqos.market_data.security_master import MockSecurityMaster
from gqos.accounting.attribution import PerformanceAttributionEngine

class MockEventBus:
    def __init__(self):
        self.subscribers = {}
        
    def publish(self, envelope: MessageEnvelope) -> None:
        event_type = type(envelope.payload)
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                handler(envelope)
                
    def subscribe(self, event_type, handler) -> None:
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

def test_pnl_attribution_buckets():
    bus = MockEventBus()
    security_master = MockSecurityMaster({"AAPL": "Technology", "JPM": "Financials"})
    engine = PerformanceAttributionEngine(bus, security_master)
    
    # 1. Realized PnL
    bus.publish(MessageEnvelope.create(RealizedPnLEmittedEvent("s1", "AAPL", Decimal('1000.0')), version=1, correlation_id="1"))
    bus.publish(MessageEnvelope.create(RealizedPnLEmittedEvent("s2", "AAPL", Decimal('500.0')), version=1, correlation_id="2"))
    bus.publish(MessageEnvelope.create(RealizedPnLEmittedEvent("s1", "JPM", Decimal('-200.0')), version=1, correlation_id="3"))
    
    # Missing sector symbol
    bus.publish(MessageEnvelope.create(RealizedPnLEmittedEvent("s1", "UNKNOWN", Decimal('100.0')), version=1, correlation_id="4"))
    
    # 2. Fees
    bus.publish(MessageEnvelope.create(FeeChargedEvent("s1", Decimal('15.0'), "USD", "Commission"), version=1, correlation_id="5"))
    
    # 3. Slippage
    trade_evt = TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('101.0'), intended_price=Decimal('100.0'), slippage_amount=Decimal('100.0'))
    bus.publish(MessageEnvelope.create(trade_evt, version=1, correlation_id="6"))
    
    state = engine.state
    
    # Strategy Attribution
    assert state.realized_pnl_by_strategy["s1"] == Decimal('900.0') # 1000 - 200 + 100
    assert state.realized_pnl_by_strategy["s2"] == Decimal('500.0')
    
    # Symbol Attribution
    assert state.realized_pnl_by_symbol["AAPL"] == Decimal('1500.0')
    assert state.realized_pnl_by_symbol["JPM"] == Decimal('-200.0')
    assert state.realized_pnl_by_symbol["UNKNOWN"] == Decimal('100.0')
    
    # Sector Attribution
    assert state.realized_pnl_by_sector["Technology"] == Decimal('1500.0')
    assert state.realized_pnl_by_sector["Financials"] == Decimal('-200.0')
    assert state.realized_pnl_by_sector["UNCLASSIFIED"] == Decimal('100.0')
    
    # Total check
    total_strat = sum(state.realized_pnl_by_strategy.values())
    total_sym = sum(state.realized_pnl_by_symbol.values())
    total_sec = sum(state.realized_pnl_by_sector.values())
    
    assert state.total_realized_pnl == Decimal('1400.0')
    assert total_strat == total_sym == total_sec == state.total_realized_pnl
    
    # Cost Attribution
    assert state.total_fees_paid == Decimal('15.0')
    assert state.total_slippage == Decimal('100.0')

def test_twr_calculation():
    engine = PerformanceAttributionEngine(MockEventBus(), MockSecurityMaster())
    
    # Start Day 1
    t0 = datetime(2026, 1, 1)
    engine.record_nav_snapshot(t0, Decimal('100000.0'))
    
    # End Day 1: Market goes up 10%
    t1 = datetime(2026, 1, 2)
    engine.record_nav_snapshot(t1, Decimal('110000.0'))
    
    # Day 2: Deposit 50,000 immediately after snapshot t1
    # For our calculation, we assume cash flow happens in period 2
    engine.record_cash_flow(t1 + timedelta(seconds=1), Decimal('50000.0'))
    
    # End Day 2: Market goes up 10% on the total 160k (110k + 50k) -> +16k -> 176k
    t2 = datetime(2026, 1, 3)
    engine.record_nav_snapshot(t2, Decimal('176000.0'))
    
    # TWR should be exactly 21% (1.10 * 1.10 - 1)
    twr = engine.calculate_twr()
    print(f"TWR Computed: {twr}")
    assert round(twr, 4) == Decimal('0.2100')

def test_mwr_calculation():
    engine = PerformanceAttributionEngine(MockEventBus(), MockSecurityMaster())
    
    t0 = datetime(2026, 1, 1)
    t1 = datetime(2026, 1, 11) # 10 days later
    t2 = datetime(2026, 1, 31) # 30 days total
    
    # Start with 100k
    engine.record_nav_snapshot(t0, Decimal('100000.0'))
    
    # Deposit 50k on day 10
    engine.record_cash_flow(t1, Decimal('50000.0'))
    
    # End with 160k. Total Gain = 10k.
    engine.record_nav_snapshot(t2, Decimal('160000.0'))
    
    mwr = engine.calculate_mwr()
    
    # BMV = 100000
    # CF = 50000
    # EMV = 160000
    # Total CF = 50000
    # Total Days = 30
    # Days Remaining for CF = 20
    # Weight = 20/30 = 0.6666...
    # Weighted CF = 50000 * 0.6666... = 33333.3333...
    # Denominator = 100000 + 33333.3333 = 133333.3333
    # Numerator = 160000 - 100000 - 50000 = 10000
    # MWR = 10000 / 133333.3333 = 0.075
    
    assert round(mwr, 4) == Decimal('0.0750')

def test_deterministic_replay():
    bus = MockEventBus()
    engine = PerformanceAttributionEngine(bus, MockSecurityMaster({"AAPL": "Technology"}))
    
    events = [
        MessageEnvelope.create(RealizedPnLEmittedEvent("s1", "AAPL", Decimal('100.0')), version=1, correlation_id="1"),
        MessageEnvelope.create(FeeChargedEvent("s1", Decimal('5.0'), "USD", "Commission"), version=1, correlation_id="2"),
        MessageEnvelope.create(RealizedPnLEmittedEvent("s1", "AAPL", Decimal('200.0')), version=1, correlation_id="3")
    ]
    
    for env in events:
        bus.publish(env)
        
    assert engine.state.total_realized_pnl == Decimal('300.0')
    assert engine.state.realized_pnl_by_sector["Technology"] == Decimal('300.0')
    assert engine.state.total_fees_paid == Decimal('5.0')

if __name__ == "__main__":
    test_pnl_attribution_buckets()
    test_twr_calculation()
    test_mwr_calculation()
    test_deterministic_replay()
    print("M10C Attribution Engine tests passed!")
