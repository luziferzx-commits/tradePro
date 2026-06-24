from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.risk.events import ExecuteTradeCommand
from gqos.risk.assets import AssetDirectory
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine

def test_unknown_symbol_rejected():
    directory = AssetDirectory()
    
    limits = ExposureLimits(
        max_gross_exposure=Decimal('1000.0'),
        max_net_exposure=Decimal('1000.0'),
        max_symbol_exposure=Decimal('1000.0'),
        max_sector_exposure=Decimal('1000.0'),
        max_correlation_group_exposure=Decimal('1000.0')
    )
    
    engine = ExposureEngine(directory, limits)
    
    cmd = ExecuteTradeCommand("UNKNOWN_COIN", TradeDirection.BUY, Decimal('10'), Decimal('100.0'), "strat_1")
    success, l_type, reason = engine.evaluate_trade(cmd)
    
    assert not success
    assert l_type == "UNKNOWN_SYMBOL"
    assert "UNKNOWN_COIN" in reason

if __name__ == "__main__":
    test_unknown_symbol_rejected()
    print("Unknown symbol test passed!")
