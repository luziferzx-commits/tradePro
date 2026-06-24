from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.accounting.models import AccountingState, Position
from gqos.market_data.interfaces import MockMarketDataProvider, PricingUnavailableError
from gqos.accounting.valuation import ValuationEngine
from gqos.execution.stages import PortfolioSnapshotStage, StageResult
from gqos.messaging.contracts import MessageEnvelope
from gqos.sizing.events import SizePositionCommand
from gqos.execution.pipeline import PipelineContext
from gqos.portfolio.manager import PortfolioManager

def test_long_mtm_profit_loss():
    market = MockMarketDataProvider({"AAPL": Decimal('120.0')})
    state = AccountingState(strategy_id="s1")
    state.positions["s1_AAPL"] = Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0'))
    
    engine = ValuationEngine(state, market)
    val = engine.calculate_position_mtm(state.positions["s1_AAPL"])
    
    assert val.market_value == Decimal('12000.0')
    assert val.unrealized_pnl == Decimal('2000.0') # (120 - 100) * 100
    
    # Loss
    market.update_price("AAPL", Decimal('90.0'))
    val2 = engine.calculate_position_mtm(state.positions["s1_AAPL"])
    assert val2.unrealized_pnl == Decimal('-1000.0')

def test_short_mtm_profit_loss():
    market = MockMarketDataProvider({"TSLA": Decimal('40.0')})
    state = AccountingState(strategy_id="s1")
    state.positions["s1_TSLA"] = Position("s1", "TSLA", TradeDirection.SELL, Decimal('200.0'), Decimal('50.0'))
    
    engine = ValuationEngine(state, market)
    val = engine.calculate_position_mtm(state.positions["s1_TSLA"])
    
    assert val.market_value == Decimal('8000.0')
    assert val.unrealized_pnl == Decimal('2000.0') # (50 - 40) * 200
    
    # Loss
    market.update_price("TSLA", Decimal('60.0'))
    val2 = engine.calculate_position_mtm(state.positions["s1_TSLA"])
    assert val2.unrealized_pnl == Decimal('-2000.0') # (50 - 60) * 200

def test_missing_price_raises_error():
    market = MockMarketDataProvider() # empty
    state = AccountingState(strategy_id="s1")
    state.positions["s1_AAPL"] = Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0'))
    
    engine = ValuationEngine(state, market)
    try:
        engine.calculate_position_mtm(state.positions["s1_AAPL"])
        assert False, "Expected PricingUnavailableError"
    except PricingUnavailableError:
        pass

def test_strategy_nav_calculation():
    market = MockMarketDataProvider({"AAPL": Decimal('120.0'), "TSLA": Decimal('40.0')})
    state = AccountingState(strategy_id="s1")
    state.positions["s1_AAPL"] = Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')) # +2000 PnL
    state.positions["s1_TSLA"] = Position("s1", "TSLA", TradeDirection.SELL, Decimal('200.0'), Decimal('50.0')) # +2000 PnL
    
    engine = ValuationEngine(state, market)
    nav_val = engine.calculate_strategy_nav("s1", settled_cash=Decimal('50000.0'))
    
    assert nav_val.total_unrealized_pnl == Decimal('4000.0')
    assert nav_val.nav == Decimal('54000.0')

def test_portfolio_snapshot_mtm_total_equity():
    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('50000.0'))
    
    market = MockMarketDataProvider({"AAPL": Decimal('150.0')})
    state = AccountingState(strategy_id="s1")
    state.positions["s1_AAPL"] = Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')) # +5000 PnL
    
    valuation_engine = ValuationEngine(state, market)
    
    stage = PortfolioSnapshotStage(manager, valuation_engine)
    cmd = SizePositionCommand("s1", "MSFT", TradeDirection.BUY, Decimal('300.0'), Decimal('290.0'))
    env = MessageEnvelope.create(cmd, version=1, correlation_id="c1")
    
    context = PipelineContext()
    res = stage.process(env, context)
    
    assert res.continue_pipeline is True
    assert context.snapshot is not None
    assert context.snapshot.unrealized_pnl == Decimal('5000.0')
    assert context.snapshot.total_equity == Decimal('55000.0') # 50000 settled + 5000 unrealized

def test_equity_curve_snapshot():
    market = MockMarketDataProvider({"AAPL": Decimal('120.0')})
    state = AccountingState(strategy_id="s1")
    state.positions["s1_AAPL"] = Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0')) # +2000 PnL
    
    engine = ValuationEngine(state, market)
    snapshot = engine.snapshot_equity_curve("s1", Decimal('50000.0'), "2026-06-24T12:00:00Z")
    
    assert snapshot["timestamp"] == "2026-06-24T12:00:00Z"
    assert snapshot["nav"] == Decimal('52000.0')
    assert snapshot["unrealized_pnl"] == Decimal('2000.0')

def test_deterministic_replay_with_mocked_prices():
    # Similar to accounting replay but with valuation
    market = MockMarketDataProvider({"AAPL": Decimal('120.0')})
    state = AccountingState(strategy_id="s1")
    state.positions["s1_AAPL"] = Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0'))
    
    engine = ValuationEngine(state, market)
    nav_val = engine.calculate_strategy_nav("s1", Decimal('50000.0'))
    assert nav_val.nav == Decimal('52000.0')

if __name__ == "__main__":
    test_long_mtm_profit_loss()
    test_short_mtm_profit_loss()
    test_strategy_nav_calculation()
    test_portfolio_snapshot_mtm_total_equity()
    test_equity_curve_snapshot()
    test_deterministic_replay_with_mocked_prices()
    test_missing_price_raises_error()
    print("M10B MTM tests passed!")
