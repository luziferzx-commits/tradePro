import json
import os
from decimal import Decimal
from typing import Dict, Any

from gqos.common.enums import TradeDirection
from gqos.accounting.models import AccountingState, Position
from gqos.portfolio.models import PortfolioState, StrategyAllocation

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, TradeDirection):
            return obj.value
        return super().default(obj)

class LedgerSnapshotService:
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    def save_snapshot(self, accounting_state: AccountingState, portfolio_state: PortfolioState):
        snapshot = {
            "accounting": {
                "positions": {}
            },
            "portfolio": {
                "total_equity": str(portfolio_state.total_equity),
                "unallocated_cash": str(portfolio_state.unallocated_cash),
                "allocations": {}
            }
        }
        
        # Serialize positions
        for key, pos in accounting_state.positions.items():
            snapshot["accounting"]["positions"][key] = {
                "strategy_id": pos.strategy_id,
                "symbol": pos.symbol,
                "direction": pos.direction.value,
                "quantity": str(pos.quantity),
                "average_price": str(pos.average_price),
                "realized_pnl": str(pos.realized_pnl)
            }
            
        # Serialize allocations
        for strat_id, alloc in portfolio_state.allocations.items():
            snapshot["portfolio"]["allocations"][strat_id] = {
                "allocated_capital": str(alloc.allocated_capital)
            }
            
        with open(self.file_path, 'w') as f:
            json.dump(snapshot, f, cls=DecimalEncoder, indent=2)
            
    def load_snapshot(self, accounting_state: AccountingState, portfolio_state: PortfolioState) -> bool:
        if not os.path.exists(self.file_path):
            return False
            
        with open(self.file_path, 'r') as f:
            snapshot = json.load(f)
            
        # Restore accounting
        accounting_state.positions.clear()
        for key, pos_dict in snapshot["accounting"]["positions"].items():
            accounting_state.positions[key] = Position(
                strategy_id=pos_dict["strategy_id"],
                symbol=pos_dict["symbol"],
                direction=TradeDirection(pos_dict["direction"]),
                quantity=Decimal(pos_dict["quantity"]),
                average_price=Decimal(pos_dict["average_price"]),
                realized_pnl=Decimal(pos_dict["realized_pnl"])
            )
            
        # Restore portfolio
        portfolio_state.total_equity = Decimal(snapshot["portfolio"]["total_equity"])
        portfolio_state.unallocated_cash = Decimal(snapshot["portfolio"]["unallocated_cash"])
        portfolio_state.allocations.clear()
        for strat_id, alloc_dict in snapshot["portfolio"]["allocations"].items():
            portfolio_state.allocations[strat_id] = StrategyAllocation(
                strategy_id=strat_id,
                allocated_capital=Decimal(alloc_dict["allocated_capital"])
            )
            
        return True
