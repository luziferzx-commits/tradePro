from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.risk.events import ExecuteTradeCommand, TradeExecutedEvent
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine

def test_symbol_sector_corr_limits():
    directory = AssetDirectory()
    directory.register_asset(AssetMetadata("NVDA", "Tech", "Equity", "Tech-MegaCaps"))
    directory.register_asset(AssetMetadata("AMD", "Tech", "Equity", "Tech-MegaCaps"))
    
    limits = ExposureLimits(
        max_gross_exposure=Decimal('10000.0'),
        max_net_exposure=Decimal('10000.0'),
        max_symbol_exposure=Decimal('200.0'),
        max_sector_exposure=Decimal('300.0'),
        max_correlation_group_exposure=Decimal('350.0')
    )
    
    engine = ExposureEngine(directory, limits)
    
    # NVDA allowed up to 200
    cmd1 = ExecuteTradeCommand("NVDA", TradeDirection.BUY, Decimal('10'), Decimal('200.0'), "s1")
    success, _, _ = engine.evaluate_trade(cmd1)
    assert success
    engine.apply_trade(TradeExecutedEvent("s1", "NVDA", TradeDirection.BUY, Decimal('10'), Decimal('20.0')))
    
    # NVDA over 200 blocked (Symbol Limit)
    cmd2 = ExecuteTradeCommand("NVDA", TradeDirection.BUY, Decimal('1'), Decimal('20.0'), "s1")
    success, l_type, _ = engine.evaluate_trade(cmd2)
    assert not success
    assert l_type == "SYMBOL_EXPOSURE"
    
    # AMD allowed up to 100 (Sector limit is 300, we already have 200 NVDA)
    cmd3 = ExecuteTradeCommand("AMD", TradeDirection.BUY, Decimal('5'), Decimal('100.0'), "s1")
    success, _, _ = engine.evaluate_trade(cmd3)
    assert success
    engine.apply_trade(TradeExecutedEvent("s1", "AMD", TradeDirection.BUY, Decimal('5'), Decimal('20.0')))
    
    # AMD more blocked (Sector Limit)
    cmd4 = ExecuteTradeCommand("AMD", TradeDirection.BUY, Decimal('1'), Decimal('20.0'), "s1")
    success, l_type, _ = engine.evaluate_trade(cmd4)
    assert not success
    assert l_type == "SECTOR_EXPOSURE"

if __name__ == "__main__":
    test_symbol_sector_corr_limits()
    print("Symbol/Sector limit test passed!")
