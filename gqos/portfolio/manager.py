from decimal import Decimal
from typing import Optional, Tuple
from gqos.portfolio.models import PortfolioState, StrategyAllocation
from gqos.sizing.portfolio import PortfolioSnapshot

class InsufficientFundsError(Exception):
    pass

class PortfolioManager:
    def __init__(self, portfolio_id: str, initial_capital: Decimal):
        self.state = PortfolioState(
            portfolio_id=portfolio_id,
            total_equity=initial_capital,
            unallocated_cash=initial_capital
        )
        
    def allocate_capital(self, strategy_id: str, amount: Decimal) -> StrategyAllocation:
        if amount <= Decimal('0'):
            raise ValueError("Allocation amount must be > 0")
            
        if self.state.unallocated_cash < amount:
            raise InsufficientFundsError(f"Insufficient unallocated cash. Requested: {amount}, Available: {self.state.unallocated_cash}")
            
        if strategy_id not in self.state.allocations:
            self.state.allocations[strategy_id] = StrategyAllocation(strategy_id=strategy_id, allocated_capital=Decimal('0'))
            
        alloc = self.state.allocations[strategy_id]
        alloc.allocated_capital += amount
        self.state.unallocated_cash -= amount
        
        return alloc
        
    def reserve_cash(self, strategy_id: str, amount: Decimal) -> Tuple[bool, str]:
        if strategy_id not in self.state.allocations:
            return False, f"Strategy {strategy_id} has no capital allocation"
            
        alloc = self.state.allocations[strategy_id]
        
        if alloc.buying_power < amount:
            return False, f"Insufficient buying power for strategy {strategy_id}. Requested: {amount}, Available: {alloc.buying_power}"
            
        alloc.reserved_cash += amount
        return True, ""
        
    def release_cash(self, strategy_id: str, amount: Decimal) -> Tuple[bool, str]:
        if strategy_id not in self.state.allocations:
            return False, f"Strategy {strategy_id} has no capital allocation"
            
        alloc = self.state.allocations[strategy_id]
        
        if alloc.reserved_cash < amount:
            return False, f"Cannot release more cash than is reserved. Requested release: {amount}, Reserved: {alloc.reserved_cash}"
            
        alloc.reserved_cash -= amount
        return True, ""
        
    def generate_snapshot(self, strategy_id: str, unrealized_pnl: Decimal = Decimal('0')) -> PortfolioSnapshot:
        if strategy_id not in self.state.allocations:
            raise ValueError(f"Strategy {strategy_id} has no capital allocation")
            
        alloc = self.state.allocations[strategy_id]
        
        # M10B: Total Equity = Settled Capital + Unrealized PnL
        total_equity = alloc.allocated_capital + unrealized_pnl
        
        return PortfolioSnapshot(
            total_equity=total_equity, # Localized to the strategy's bucket
            available_cash=alloc.buying_power,    # This acts as available cash
            margin_used=alloc.utilized_capital,
            buying_power=alloc.buying_power,
            unrealized_pnl=unrealized_pnl
        )

    def apply_realized_pnl(self, strategy_id: str, pnl_amount: Decimal) -> Tuple[bool, str]:
        if strategy_id not in self.state.allocations:
            return False, f"Strategy {strategy_id} has no capital allocation"
            
        alloc = self.state.allocations[strategy_id]
        alloc.allocated_capital += pnl_amount
        # Portfolio global state
        self.state.total_equity += pnl_amount
        self.state.unallocated_cash += pnl_amount # PnL is cash
        
        return True, ""
