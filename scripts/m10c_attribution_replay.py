from decimal import Decimal
from datetime import datetime
from gqos.messaging.contracts import MessageEnvelope
from gqos.common.enums import TradeDirection
from gqos.accounting.events import RealizedPnLEmittedEvent, FeeChargedEvent
from gqos.risk.events import TradeExecutedEvent
from gqos.market_data.security_master import MockSecurityMaster
from gqos.accounting.attribution import PerformanceAttributionEngine

class PrintEventBus:
    def subscribe(self, event_type, handler) -> None:
        pass
    def publish(self, envelope: MessageEnvelope) -> None:
        pass

def main():
    print("========================================")
    print(" M10C Performance Attribution Replay")
    print("========================================")
    
    bus = PrintEventBus()
    security_master = MockSecurityMaster({"AAPL": "Technology", "JPM": "Financials", "TSLA": "Consumer Discretionary"})
    engine = PerformanceAttributionEngine(bus, security_master)
    
    events = [
        # Strategy 1 trades
        RealizedPnLEmittedEvent("s1", "AAPL", Decimal('1500.0')),
        FeeChargedEvent("s1", Decimal('10.0'), "USD", "Commission"),
        TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('100.0'), Decimal('149.0'), intended_price=Decimal('150.0'), slippage_amount=Decimal('100.0')),
        RealizedPnLEmittedEvent("s1", "JPM", Decimal('-300.0')),
        
        # Strategy 2 trades
        RealizedPnLEmittedEvent("s2", "TSLA", Decimal('800.0')),
        FeeChargedEvent("s2", Decimal('5.0'), "USD", "Commission"),
        
        # Unclassified symbol
        RealizedPnLEmittedEvent("s1", "UNKNOWN", Decimal('50.0'))
    ]
    
    print("\n[Replaying PnL, Fee, and Slippage Events...]\n")
    for i, event in enumerate(events, 1):
        env = MessageEnvelope.create(event, version=1, correlation_id=str(i))
        print(f"Applying: {type(event).__name__} -> {event}")
        if isinstance(event, RealizedPnLEmittedEvent):
            engine._on_realized_pnl(env)
        elif isinstance(event, FeeChargedEvent):
            engine._on_fee_charged(env)
        elif isinstance(event, TradeExecutedEvent):
            engine._on_trade_executed(env)

    print("\n========================================")
    print(" ATTRIBUTION BUCKETS")
    print("========================================")
    
    state = engine.state
    print(f"\nTotal Realized PnL: {state.total_realized_pnl}")
    print(f"Total Fees Paid:    {state.total_fees_paid}")
    print(f"Total Slippage:     {state.total_slippage}")
    
    print("\n--- Strategy Attribution ---")
    for k, v in state.realized_pnl_by_strategy.items():
        print(f"  [{k}]: {v}")
        
    print("\n--- Sector Attribution ---")
    for k, v in state.realized_pnl_by_sector.items():
        print(f"  [{k}]: {v}")
        
    print("\n--- Symbol Attribution ---")
    for k, v in state.realized_pnl_by_symbol.items():
        print(f"  [{k}]: {v}")

    print("\n========================================")
    print(" TWR / MWR DEMONSTRATION")
    print("========================================")
    
    t0 = datetime(2026, 1, 1)
    t1 = datetime(2026, 1, 10)
    t2 = datetime(2026, 1, 30)
    
    engine.record_nav_snapshot(t0, Decimal('100000.0'))
    engine.record_cash_flow(t1, Decimal('50000.0'))
    engine.record_nav_snapshot(t1, Decimal('110000.0')) # Before cash flow
    engine.record_nav_snapshot(t2, Decimal('176000.0'))
    
    twr = engine.calculate_twr()
    mwr = engine.calculate_mwr()
    
    print(f"\nTWR (Time-Weighted Return):  {twr * 100:.2f}%")
    print(f"MWR (Money-Weighted Return): {mwr * 100:.2f}%")

if __name__ == "__main__":
    main()
