from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.risk.events import ExecuteTradeCommand, TradeRejectedByExposureLimit
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine

def test_gross_net_exposure_limits():
    directory = AssetDirectory()
    directory.register_asset(AssetMetadata("AAPL", "Tech", "Equity", "Tech-MegaCaps"))
    directory.register_asset(AssetMetadata("TSLA", "Auto", "Equity", "Consumer-Disc"))
    
    limits = ExposureLimits(
        max_gross_exposure=Decimal('1000.0'),
        max_net_exposure=Decimal('500.0'),
        max_symbol_exposure=Decimal('1000.0'),
        max_sector_exposure=Decimal('1000.0'),
        max_correlation_group_exposure=Decimal('1000.0')
    )
    
    engine = ExposureEngine(directory, limits)
    
    # 1. Gross allowed
    cmd1 = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('10'), Decimal('400.0'), "strat_1") # +400 gross, +400 net
    success, l_type, reason = engine.evaluate_trade(cmd1)
    assert success
    
    # Simulate execution
    from gqos.risk.events import TradeExecutedEvent
    engine.apply_trade(TradeExecutedEvent(strategy_id="strat_1", symbol="AAPL", direction=TradeDirection.BUY, quantity=Decimal('10'), execution_price=Decimal('40.0')))
    
    assert engine._state.gross_exposure == Decimal('400.0')
    assert engine._state.net_exposure == Decimal('400.0')
    
    # 2. Net Exceeded
    cmd2 = ExecuteTradeCommand("TSLA", TradeDirection.BUY, Decimal('10'), Decimal('200.0'), "strat_1") # +200 gross, +200 net => Gross=600, Net=600 (LIMIT 500)
    success, l_type, reason = engine.evaluate_trade(cmd2)
    assert not success
    assert l_type == "NET_EXPOSURE"
    
    # 3. Short Trade decreases net, increases gross
    cmd3 = ExecuteTradeCommand("TSLA", TradeDirection.SELL, Decimal('10'), Decimal('200.0'), "strat_1") # +200 gross, -200 net => Gross=600, Net=200
    success, l_type, reason = engine.evaluate_trade(cmd3)
    assert success
    
    engine.apply_trade(TradeExecutedEvent(strategy_id="strat_1", symbol="TSLA", direction=TradeDirection.SELL, quantity=Decimal('10'), execution_price=Decimal('20.0')))
    assert engine._state.gross_exposure == Decimal('600.0')
    assert engine._state.net_exposure == Decimal('200.0')
    
    # 4. Gross Exceeded
    cmd4 = ExecuteTradeCommand("TSLA", TradeDirection.SELL, Decimal('30'), Decimal('600.0'), "strat_1") # Gross=1200, Limit 1000
    success, l_type, reason = engine.evaluate_trade(cmd4)
    assert not success
    assert l_type == "GROSS_EXPOSURE"

if __name__ == "__main__":
    test_gross_net_exposure_limits()
    print("Gross/Net exposure test passed!")
