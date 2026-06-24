from decimal import Decimal
import random
from gqos.common.enums import TradeDirection
from gqos.accounting.models import Position
from gqos.risk.var.historical import HistoricalVaREngine

def test_empty_portfolio():
    engine = HistoricalVaREngine()
    res_var = engine.calculate_var([], {}, Decimal('0.95'))
    res_cvar = engine.calculate_cvar([], {}, Decimal('0.95'))
    assert res_var.var_amount == Decimal('0')
    assert res_cvar.cvar_amount == Decimal('0')

def test_single_position_known_result():
    engine = HistoricalVaREngine()
    pos = Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')) # Value = 10k
    
    # Let's give exactly 10 returns: 5 positive, 5 negative.
    # 0: -0.10 (loss 1000)
    # 1: -0.05 (loss 500)
    # 2: -0.02 (loss 200)
    # 3: -0.01 (loss 100)
    # 4:  0.00
    # 5:  0.01
    # 6:  0.02
    # 7:  0.05
    # 8:  0.10
    # 9:  0.20
    
    returns = [Decimal('-0.10'), Decimal('-0.05'), Decimal('-0.02'), Decimal('-0.01'), Decimal('0.00'), 
               Decimal('0.01'), Decimal('0.02'), Decimal('0.05'), Decimal('0.10'), Decimal('0.20')]
               
    # Conf = 0.90 -> Tail prob = 0.10. 10 samples -> 10 * 0.10 = 1. index = ceil(1) - 1 = 0
    # Worst loss is -1000. So VaR = 1000.
    res_var = engine.calculate_var([pos], {"AAPL": returns}, Decimal('0.90'))
    assert res_var.var_amount == Decimal('1000.0')
    
    # CVaR = Average of the tail. Tail count = max(1, ceil(10 * 0.10)) = 1.
    # Average of [-1000] is -1000. CVaR = 1000.
    res_cvar = engine.calculate_cvar([pos], {"AAPL": returns}, Decimal('0.90'))
    assert res_cvar.cvar_amount == Decimal('1000.0')

def test_position_scaling():
    engine = HistoricalVaREngine()
    returns = [Decimal('-0.10'), Decimal('-0.05'), Decimal('-0.02'), Decimal('-0.01'), Decimal('0.00')] * 2
    
    pos1 = Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')) # 10k
    res_var1 = engine.calculate_var([pos1], {"AAPL": returns}, Decimal('0.90'))
    
    pos2 = Position("s1", "AAPL", TradeDirection.BUY, Decimal('200.0'), Decimal('100.0')) # 20k
    res_var2 = engine.calculate_var([pos2], {"AAPL": returns}, Decimal('0.90'))
    
    assert res_var2.var_amount == res_var1.var_amount * Decimal('2')

def test_confidence_sweep():
    engine = HistoricalVaREngine()
    pos = Position("s1", "AAPL", TradeDirection.BUY, Decimal('10.0'), Decimal('100.0')) # 1k value
    # Generate 100 samples from -50% to +49%
    returns = [Decimal(f"{(i - 50) / 100.0}") for i in range(100)]
    
    # Sorted losses:
    # returns[0] = -0.50 -> loss 500
    # returns[1] = -0.49 -> loss 490
    # ...
    # returns[10] = -0.40 -> loss 400
    
    res_90 = engine.calculate_var([pos], {"AAPL": returns}, Decimal('0.90'))
    res_95 = engine.calculate_var([pos], {"AAPL": returns}, Decimal('0.95'))
    res_99 = engine.calculate_var([pos], {"AAPL": returns}, Decimal('0.99'))
    
    assert res_99.var_amount > res_95.var_amount > res_90.var_amount

def test_distribution_length_and_replay():
    engine = HistoricalVaREngine()
    pos = Position("s1", "AAPL", TradeDirection.BUY, Decimal('1.0'), Decimal('100.0'))
    
    for length in [100, 1000, 10000]:
        random.seed(length) # For deterministic generation
        returns = [Decimal(str(random.uniform(-0.1, 0.1))) for _ in range(length)]
        
        # Test 1
        res1 = engine.calculate_var([pos], {"AAPL": returns}, Decimal('0.95'))
        
        # Identical Replay
        res2 = engine.calculate_var([pos], {"AAPL": returns}, Decimal('0.95'))
        assert res1.var_amount == res2.var_amount
        
        cvar = engine.calculate_cvar([pos], {"AAPL": returns}, Decimal('0.95'))
        assert cvar.cvar_amount >= res1.var_amount # CVaR >= VaR

if __name__ == "__main__":
    test_empty_portfolio()
    test_single_position_known_result()
    test_position_scaling()
    test_confidence_sweep()
    test_distribution_length_and_replay()
    print("M11A Historical VaR Engine tests passed!")
