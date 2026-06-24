from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.exposure import ExposureLimits
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.events import TradeExecutedEvent

def test_delta_logic_flips():
    directory = AssetDirectory()
    directory.register_asset(AssetMetadata("TSLA", "Auto", "Equity", "Growth"))
    
    limits = ExposureLimits(
        max_gross_exposure=Decimal('10000.0'),
        max_net_exposure=Decimal('10000.0'),
        max_symbol_exposure=Decimal('10000.0'),
        max_sector_exposure=Decimal('10000.0'),
        max_correlation_group_exposure=Decimal('10000.0')
    )
    
    engine = ExposureEngine(directory, limits)
    
    # 1. Long 100 @ 10
    engine.apply_trade(TradeExecutedEvent("s1", "TSLA", TradeDirection.BUY, Decimal('100'), Decimal('10.0')))
    pos = engine._snapshot.positions["TSLA"]
    assert pos.quantity == Decimal('100')
    assert pos.average_entry_price == Decimal('10.0')
    assert engine._snapshot.gross_exposure == Decimal('1000.0')
    
    # 2. Add Long 50 @ 16
    engine.apply_trade(TradeExecutedEvent("s1", "TSLA", TradeDirection.BUY, Decimal('50'), Decimal('16.0')))
    pos = engine._snapshot.positions["TSLA"]
    assert pos.quantity == Decimal('150')
    # (1000 + 800) / 150 = 12.0
    assert pos.average_entry_price == Decimal('12.0')
    assert engine._snapshot.gross_exposure == Decimal('2400.0')
    
    # 3. Reduce Long by 100 @ 20
    engine.apply_trade(TradeExecutedEvent("s1", "TSLA", TradeDirection.SELL, Decimal('100'), Decimal('20.0')))
    pos = engine._snapshot.positions["TSLA"]
    assert pos.quantity == Decimal('50')
    assert pos.average_entry_price == Decimal('12.0') # Unchanged
    assert engine._snapshot.gross_exposure == Decimal('1000.0') # 50 * 20
    
    # 4. Flip to short! Sell 100 @ 15.
    # We have 50 long. Selling 100 makes us 50 short.
    engine.apply_trade(TradeExecutedEvent("s1", "TSLA", TradeDirection.SELL, Decimal('100'), Decimal('15.0')))
    pos = engine._snapshot.positions["TSLA"]
    assert pos.quantity == Decimal('-50')
    assert pos.average_entry_price == Decimal('15.0') # New cost basis
    assert engine._snapshot.gross_exposure == Decimal('750.0') # |-50 * 15|
    assert engine._snapshot.net_exposure == Decimal('-750.0')

if __name__ == "__main__":
    test_delta_logic_flips()
    print("Delta Flip Test Passed!")
