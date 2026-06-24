from decimal import Decimal
from typing import List
from gqos.common.enums import TradeDirection
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import TradeExecutedEvent
from gqos.accounting.engine import AccountingEngine
from gqos.accounting.fee_model import MockFeeModel
from gqos.accounting.fx import MockFxConverter

class PrintEventBus:
    def subscribe(self, event_type, handler) -> None:
        pass
    def publish(self, envelope: MessageEnvelope) -> None:
        event = envelope.payload
        print(f"EVENT EMITTED: {type(event).__name__}")
        for k, v in event.__dict__.items():
            print(f"  {k}: {v}")

def main():
    print("========================================")
    print(" M10A Accounting Replay Script")
    print("========================================")
    
    bus = PrintEventBus()
    fee_model = MockFeeModel(commission_per_share=Decimal('0.01'))
    fx = MockFxConverter()
    engine = AccountingEngine(bus, fee_model, fx)
    
    trades = [
        # Open Long 100 @ 100
        TradeExecutedEvent("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')),
        # Partial Close 40 @ 150
        TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('40.0'), Decimal('150.0')),
        # Open Short 200 @ 50 (different symbol)
        TradeExecutedEvent("s1", "TSLA", TradeDirection.SELL, Decimal('200.0'), Decimal('50.0')),
        # Flip Long AAPL to Short (Close 60, Open 40 Short) @ 120
        TradeExecutedEvent("s1", "AAPL", TradeDirection.SELL, Decimal('100.0'), Decimal('120.0'))
    ]
    
    print("\n[Replaying Trade Events...]\n")
    for i, trade in enumerate(trades, 1):
        print(f"\n--- Trade {i}: {trade.direction.name} {trade.quantity} {trade.symbol} @ {trade.execution_price} ---")
        engine._handle_trade_executed(MessageEnvelope.create(trade, version=1, correlation_id=str(i)))

    print("\n========================================")
    print(" FINAL LEDGER STATE")
    print("========================================")
    print("\nPositions:")
    for pos_key, pos in engine.state.positions.items():
        print(f"  [{pos_key}] {pos.direction.name} {pos.quantity} @ {pos.average_price} (Realized PnL: {pos.realized_pnl})")
        
    print("\nCash Accounts:")
    for cash_key, cash in engine.state.cash.items():
        print(f"  [{cash_key}] {cash.currency}: {cash.balance}")

if __name__ == "__main__":
    main()
