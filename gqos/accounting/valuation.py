from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List
from gqos.common.enums import TradeDirection
from gqos.accounting.models import Position, AccountingState
from gqos.market_data.interfaces import IMarketDataProvider, PricingUnavailableError

@dataclass
class PositionValuation:
    symbol: str
    direction: TradeDirection
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal

@dataclass
class StrategyValuation:
    strategy_id: str
    settled_cash: Decimal
    total_market_value: Decimal
    total_unrealized_pnl: Decimal
    nav: Decimal # Net Asset Value = settled_cash + total_unrealized_pnl (or settled_cash + realized + unrealized)
    positions: List[PositionValuation]

class ValuationEngine:
    def __init__(self, accounting_state: AccountingState, market_data: IMarketDataProvider):
        self._state = accounting_state
        self._market_data = market_data
        
    def calculate_position_mtm(self, position: Position) -> PositionValuation:
        current_price = self._market_data.get_latest_price(position.symbol)
        
        market_value = position.quantity * current_price
        
        if position.direction == TradeDirection.BUY:
            unrealized_pnl = (current_price - position.average_price) * position.quantity
        else: # SELL
            unrealized_pnl = (position.average_price - current_price) * position.quantity
            
        return PositionValuation(
            symbol=position.symbol,
            direction=position.direction,
            quantity=position.quantity,
            average_price=position.average_price,
            current_price=current_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl
        )
        
    def calculate_strategy_nav(self, strategy_id: str, settled_cash: Decimal) -> StrategyValuation:
        total_market_value = Decimal('0')
        total_unrealized_pnl = Decimal('0')
        position_valuations = []
        
        # In AccountingState, positions are stored as f"{strategy_id}_{symbol}"
        prefix = f"{strategy_id}_"
        
        for pos_key, position in self._state.positions.items():
            if pos_key.startswith(prefix):
                try:
                    val = self.calculate_position_mtm(position)
                    position_valuations.append(val)
                    total_market_value += val.market_value
                    total_unrealized_pnl += val.unrealized_pnl
                except PricingUnavailableError:
                    # Depending on policy, we could use average_price as a fallback or just propagate
                    raise
                    
        nav = settled_cash + total_unrealized_pnl
        
        return StrategyValuation(
            strategy_id=strategy_id,
            settled_cash=settled_cash,
            total_market_value=total_market_value,
            total_unrealized_pnl=total_unrealized_pnl,
            nav=nav,
            positions=position_valuations
        )
        
    def snapshot_equity_curve(self, strategy_id: str, settled_cash: Decimal, timestamp: str) -> Dict:
        """
        Explicit call to snapshot the equity curve for periodic logging.
        Returns a serializable dictionary of the current NAV snapshot.
        """
        val = self.calculate_strategy_nav(strategy_id, settled_cash)
        return {
            "strategy_id": strategy_id,
            "timestamp": timestamp,
            "nav": val.nav,
            "unrealized_pnl": val.total_unrealized_pnl,
            "settled_cash": val.settled_cash,
            "positions_count": len(val.positions)
        }
