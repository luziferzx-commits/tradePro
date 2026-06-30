from decimal import Decimal
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple
from gqos.portfolio.models import PortfolioState, StrategyAllocation
from gqos.sizing.portfolio import PortfolioSnapshot

class InsufficientFundsError(Exception):
    pass

@dataclass(frozen=True)
class CashReservation:
    strategy_id: str
    symbol: str
    amount: Decimal
    allocation_id: str

class PortfolioManager:
    def __init__(self, portfolio_id: str, initial_capital: Decimal):
        self.state = PortfolioState(
            portfolio_id=portfolio_id,
            total_equity=initial_capital,
            unallocated_cash=initial_capital
        )
        self._cash_reservations_by_symbol: Dict[str, Deque[CashReservation]] = defaultdict(deque)
        self._cash_reservations_by_id: Dict[str, CashReservation] = {}
        
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
        
    def reserve_cash(
        self,
        strategy_id: str,
        amount: Decimal,
        symbol: Optional[str] = None,
        allocation_id: str = "",
    ) -> Tuple[bool, str]:
        if strategy_id not in self.state.allocations:
            return False, f"Strategy {strategy_id} has no capital allocation"
            
        alloc = self.state.allocations[strategy_id]
        
        if alloc.buying_power < amount:
            return False, f"Insufficient buying power for strategy {strategy_id}. Requested: {amount}, Available: {alloc.buying_power}"
            
        alloc.reserved_cash += amount
        if symbol:
            reservation = CashReservation(
                strategy_id=strategy_id,
                symbol=symbol,
                amount=amount,
                allocation_id=allocation_id,
            )
            self._cash_reservations_by_symbol[symbol].append(reservation)
            if allocation_id:
                self._cash_reservations_by_id[allocation_id] = reservation
        return True, ""
        
    def release_cash(self, strategy_id: str, amount: Decimal) -> Tuple[bool, str]:
        if strategy_id not in self.state.allocations:
            return False, f"Strategy {strategy_id} has no capital allocation"
            
        alloc = self.state.allocations[strategy_id]
        
        if alloc.reserved_cash < amount:
            return False, f"Cannot release more cash than is reserved. Requested release: {amount}, Reserved: {alloc.reserved_cash}"
            
        alloc.reserved_cash -= amount
        self._remove_tracked_reservation(strategy_id, amount)
        return True, ""

    def release_cash_for_symbol(self, symbol: str) -> Tuple[bool, str, Optional[CashReservation]]:
        queue = self._cash_reservations_by_symbol.get(symbol)
        if not queue:
            return False, f"No tracked cash reservation for symbol {symbol}", None

        reservation = queue[0]
        return self._release_cash_reservation(reservation)

    def release_cash_for_allocation(self, allocation_id: str) -> Tuple[bool, str, Optional[CashReservation]]:
        reservation = self._cash_reservations_by_id.get(allocation_id)
        if reservation is None:
            return False, f"No tracked cash reservation for allocation {allocation_id}", None
        return self._release_cash_reservation(reservation)

    def rebuild_cash_reservations_from_positions(self, positions) -> None:
        for alloc in self.state.allocations.values():
            alloc.reserved_cash = Decimal('0')
        self._cash_reservations_by_symbol.clear()
        self._cash_reservations_by_id.clear()

        for idx, position in enumerate(positions):
            strategy_id = getattr(position, "strategy_id", "")
            symbol = getattr(position, "symbol", "")
            quantity = getattr(position, "quantity", Decimal('0'))
            average_price = getattr(position, "average_price", Decimal('0'))
            if not strategy_id or not symbol or strategy_id not in self.state.allocations:
                continue

            amount = abs(Decimal(str(quantity)) * Decimal(str(average_price)))
            if amount <= Decimal('0'):
                continue

            allocation_id = f"reconciled:{strategy_id}:{symbol}:{idx}"
            alloc = self.state.allocations[strategy_id]
            alloc.reserved_cash += amount
            reservation = CashReservation(
                strategy_id=strategy_id,
                symbol=symbol,
                amount=amount,
                allocation_id=allocation_id,
            )
            self._cash_reservations_by_symbol[symbol].append(reservation)
            self._cash_reservations_by_id[allocation_id] = reservation

    def _release_cash_reservation(self, reservation: CashReservation) -> Tuple[bool, str, Optional[CashReservation]]:
        if reservation.strategy_id not in self.state.allocations:
            return False, f"Strategy {reservation.strategy_id} has no capital allocation", reservation

        alloc = self.state.allocations[reservation.strategy_id]
        if alloc.reserved_cash < reservation.amount:
            return False, (
                f"Cannot release more cash than is reserved. "
                f"Requested release: {reservation.amount}, Reserved: {alloc.reserved_cash}"
            ), reservation

        alloc.reserved_cash -= reservation.amount
        self._remove_tracked_reservation(reservation.strategy_id, reservation.amount, reservation.allocation_id)
        return True, "", reservation

    def _remove_tracked_reservation(self, strategy_id: str, amount: Decimal, allocation_id: str = "") -> None:
        if allocation_id:
            self._cash_reservations_by_id.pop(allocation_id, None)

        for symbol, queue in list(self._cash_reservations_by_symbol.items()):
            for idx, reservation in enumerate(queue):
                id_matches = allocation_id and reservation.allocation_id == allocation_id
                value_matches = reservation.strategy_id == strategy_id and reservation.amount == amount
                if id_matches or value_matches:
                    del queue[idx]
                    if reservation.allocation_id:
                        self._cash_reservations_by_id.pop(reservation.allocation_id, None)
                    if not queue:
                        self._cash_reservations_by_symbol.pop(symbol, None)
                    return
        
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
