from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Optional

@dataclass
class StrategyAllocation:
    strategy_id: str
    allocated_capital: Decimal
    reserved_cash: Decimal = Decimal('0')
    utilized_capital: Decimal = Decimal('0')
    
    @property
    def buying_power(self) -> Decimal:
        return self.allocated_capital - self.reserved_cash - self.utilized_capital

@dataclass
class PortfolioState:
    portfolio_id: str
    total_equity: Decimal
    unallocated_cash: Decimal
    allocations: Dict[str, StrategyAllocation] = field(default_factory=dict)
