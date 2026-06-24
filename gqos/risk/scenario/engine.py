from decimal import Decimal
from typing import List, Dict
from gqos.common.enums import TradeDirection
from gqos.accounting.models import Position
from gqos.market_data.security_master import ISecurityMaster
from gqos.risk.scenario.interfaces import IScenario
from gqos.risk.scenario.models import ScenarioResult

class ScenarioEngine:
    
    def evaluate_scenario(self, positions: List[Position], scenario: IScenario, security_master: ISecurityMaster) -> ScenarioResult:
        total_impact = Decimal('0')
        total_mkt_val = Decimal('0')
        
        impact_by_strategy: Dict[str, Decimal] = {}
        impact_by_symbol: Dict[str, Decimal] = {}
        impact_by_sector: Dict[str, Decimal] = {}

        for pos in positions:
            # 1. Resolve Sector
            sector = security_master.get_sector(pos.symbol)
            
            # 2. Get Shock (Priority: Symbol > Sector > Global) handled by Scenario implementation
            shock = scenario.get_shock(pos.symbol, sector) or Decimal('0')
            
            # 3. Calculate Base Value and Impact
            base_value = pos.quantity * pos.average_price
            total_mkt_val += base_value
            
            if pos.direction == TradeDirection.BUY:
                impact = base_value * shock
            else:
                impact = base_value * -shock
                
            # 4. Accumulate Impact
            total_impact += impact
            
            impact_by_strategy[pos.strategy_id] = impact_by_strategy.get(pos.strategy_id, Decimal('0')) + impact
            impact_by_symbol[pos.symbol] = impact_by_symbol.get(pos.symbol, Decimal('0')) + impact
            impact_by_sector[sector] = impact_by_sector.get(sector, Decimal('0')) + impact

        # 5. Portfolio Loss Percent
        loss_pct = Decimal('0')
        if total_mkt_val > Decimal('0'):
            loss_pct = total_impact / total_mkt_val

        return ScenarioResult(
            scenario_id=scenario.metadata.scenario_id,
            total_impact_amount=total_impact,
            total_market_value=total_mkt_val,
            portfolio_loss_percent=loss_pct,
            impact_by_strategy=impact_by_strategy,
            impact_by_symbol=impact_by_symbol,
            impact_by_sector=impact_by_sector
        )
