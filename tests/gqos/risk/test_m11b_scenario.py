from decimal import Decimal
from datetime import datetime
from gqos.common.enums import TradeDirection
from gqos.accounting.models import Position
from gqos.market_data.security_master import MockSecurityMaster
from gqos.risk.scenario.models import ScenarioMetadata
from gqos.risk.scenario.historical import HistoricalScenario, HypotheticalScenario
from gqos.risk.scenario.composite import CompositeScenario
from gqos.risk.scenario.engine import ScenarioEngine
from gqos.risk.scenario.registry import ScenarioRegistry

def create_mock_metadata(scenario_id: str) -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id=scenario_id,
        version="1.0.0",
        author="Quant",
        created_at=datetime.utcnow().isoformat(),
        description="Test Scenario",
        assumptions="None"
    )

def test_priority_resolution():
    meta = create_mock_metadata("PRIORITY_TEST")
    scenario = HypotheticalScenario(
        metadata=meta,
        symbol_shocks={"AAPL": Decimal('-0.30')}, # Symbol: -30%
        sector_shocks={"Technology": Decimal('-0.20')}, # Sector: -20%
        global_shock=Decimal('-0.10') # Global: -10%
    )
    
    # AAPL is Technology, should get -30%
    assert scenario.get_shock("AAPL", "Technology") == Decimal('-0.30')
    # MSFT is Technology, should get -20%
    assert scenario.get_shock("MSFT", "Technology") == Decimal('-0.20')
    # JPM is Financials, should get -10%
    assert scenario.get_shock("JPM", "Financials") == Decimal('-0.10')

def test_unknown_symbol_zero_shock():
    meta = create_mock_metadata("UNKNOWN_SYMBOL")
    # Only AAPL is shocked, no global shock
    scenario = HypotheticalScenario(metadata=meta, symbol_shocks={"AAPL": Decimal('-0.30')}, sector_shocks={})
    
    engine = ScenarioEngine()
    sec_master = MockSecurityMaster({"MSFT": "Technology", "JPM": "Financials", "AAPL": "Technology"})
    
    pos = Position("s1", "UNKNOWN_CORP", TradeDirection.BUY, Decimal('10.0'), Decimal('100.0'))
    
    result = engine.evaluate_scenario([pos], scenario, sec_master)
    assert result.total_impact_amount == Decimal('0')

def test_unknown_sector_default_shock():
    meta = create_mock_metadata("UNKNOWN_SECTOR")
    scenario = HypotheticalScenario(
        metadata=meta, 
        symbol_shocks={}, 
        sector_shocks={"Technology": Decimal('-0.20')}, 
        global_shock=Decimal('-0.05')
    )
    
    engine = ScenarioEngine()
    sec_master = MockSecurityMaster({"MSFT": "Technology", "JPM": "Financials", "AAPL": "Technology"})
    
    # MSFT is Tech in MockSecurityMaster
    pos1 = Position("s1", "MSFT", TradeDirection.BUY, Decimal('10.0'), Decimal('100.0')) # Value = 1000
    # JPM is Financials in MockSecurityMaster
    pos2 = Position("s1", "JPM", TradeDirection.BUY, Decimal('10.0'), Decimal('100.0')) # Value = 1000
    
    result = engine.evaluate_scenario([pos1, pos2], scenario, sec_master)
    
    # MSFT: 1000 * -0.20 = -200
    # JPM: 1000 * -0.05 = -50
    # Total = -250
    assert result.impact_by_symbol["MSFT"] == Decimal('-200.0')
    assert result.impact_by_symbol["JPM"] == Decimal('-50.0')
    assert result.total_impact_amount == Decimal('-250.0')

def test_composite_scenario():
    meta1 = create_mock_metadata("S1")
    s1 = HypotheticalScenario(meta1, symbol_shocks={"AAPL": Decimal('-0.10')}, sector_shocks={})
    
    meta2 = create_mock_metadata("S2")
    s2 = HypotheticalScenario(meta2, symbol_shocks={}, sector_shocks={"Technology": Decimal('-0.15')}, global_shock=Decimal('0'))
    
    meta3 = create_mock_metadata("S3")
    s3 = HypotheticalScenario(meta3, symbol_shocks={}, sector_shocks={}, global_shock=Decimal('-0.05'))
    
    comp_meta = create_mock_metadata("COMPOSITE")
    comp = CompositeScenario(comp_meta, [s1, s2, s3])
    
    # AAPL (Tech): -0.10 + -0.15 + -0.05 = -0.30
    assert comp.get_shock("AAPL", "Technology") == Decimal('-0.30')
    # MSFT (Tech): None + -0.15 + -0.05 = -0.20
    assert comp.get_shock("MSFT", "Technology") == Decimal('-0.20')

def test_empty_portfolio():
    meta = create_mock_metadata("EMPTY")
    scenario = HypotheticalScenario(meta, symbol_shocks={}, sector_shocks={}, global_shock=Decimal('-0.50'))
    
    engine = ScenarioEngine()
    sec_master = MockSecurityMaster({"MSFT": "Technology", "JPM": "Financials", "AAPL": "Technology"})
    
    result = engine.evaluate_scenario([], scenario, sec_master)
    assert result.total_impact_amount == Decimal('0')
    assert result.total_market_value == Decimal('0')
    assert result.portfolio_loss_percent == Decimal('0')

def test_replay_determinism():
    meta = create_mock_metadata("REPLAY")
    scenario = HistoricalScenario(meta, symbol_shocks={"AAPL": Decimal('-0.20')}, sector_shocks={}, global_shock=Decimal('0'))
    
    engine = ScenarioEngine()
    sec_master = MockSecurityMaster({"MSFT": "Technology", "JPM": "Financials", "AAPL": "Technology"})
    
    positions = [
        Position("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('150.0')),
        Position("s2", "AAPL", TradeDirection.SELL, Decimal('50.0'), Decimal('150.0'))
    ]
    
    res1 = engine.evaluate_scenario(positions, scenario, sec_master)
    res2 = engine.evaluate_scenario(positions, scenario, sec_master)
    
    assert res1.total_impact_amount == res2.total_impact_amount
    assert res1.scenario_id == res2.scenario_id
    assert res1.portfolio_loss_percent == res2.portfolio_loss_percent

    # Buy AAPL 100 @ 150 = 15000 * -0.20 = -3000
    # Sell AAPL 50 @ 150 = 7500 * --0.20 = +1500
    # Total Impact = -1500
    assert res1.total_impact_amount == Decimal('-1500.0')

if __name__ == "__main__":
    test_priority_resolution()
    test_unknown_symbol_zero_shock()
    test_unknown_sector_default_shock()
    test_composite_scenario()
    test_empty_portfolio()
    test_replay_determinism()
    print("M11B Scenario Analysis tests passed!")
