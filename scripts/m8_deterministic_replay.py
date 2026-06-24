from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, RoundingPolicy
from gqos.sizing.policies import FixedRiskPolicy
from gqos.sizing.engine import PositionSizingEngine

def run_replay():
    print("=== M8 Deterministic Sizing Replay ===")
    
    # Simulate a stream of past strategy signals
    signals = [
        # (symbol, direction, entry, stop, expected_qty)
        ("AAPL", TradeDirection.BUY, Decimal('150.0'), Decimal('140.0'), Decimal('100')), # Loss=10, Risk=1k -> Qty=100
        ("TSLA", TradeDirection.SELL, Decimal('200.0'), Decimal('250.0'), Decimal('20')), # Loss=50, Risk=1k -> Qty=20
        ("NVDA", TradeDirection.BUY, Decimal('100.0'), Decimal('50.0'), Decimal('20')),   # Loss=50, Risk=1k -> Qty=20
    ]
    
    engine = PositionSizingEngine()
    policy = FixedRiskPolicy(risk_fraction=Decimal('0.01'), rounding=RoundingPolicy.ROUND_DOWN) # 1% risk
    capital = Decimal('100000.0') # $100k
    
    success = True
    
    for symbol, direction, entry, stop, expected_qty in signals:
        req = SizingRequest("strat_1", symbol, direction, entry, stop)
        res = engine.size_trade(req, policy, capital)
        
        print(f"Signal: {direction.name} {symbol} @ {entry} (SL: {stop})")
        print(f"Reason: {res.sizing_reason}")
        print(f"Result: {res.quantity} shares\n")
        
        if res.quantity != expected_qty:
            print(f"MISMATCH: Expected {expected_qty}, got {res.quantity}")
            success = False
            
    if success:
        print("Replay Validation: SUCCESS (All sizing deterministic)")
    else:
        print("Replay Validation: FAILED")

if __name__ == "__main__":
    run_replay()
