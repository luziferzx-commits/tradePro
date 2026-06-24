import threading
from typing import Dict, Optional, Tuple
from decimal import Decimal
from .models import RiskBudget, RiskBudgetSnapshot, AllocationRequest, AllocationResult

class RiskBudgetStore:
    """In-memory store for tracking current risk budgets with atomic updates."""
    def __init__(self):
        self._budgets: Dict[str, RiskBudget] = {}
        # Stores allocation_id -> (budget_id, amount)
        self._allocations: Dict[str, Tuple[str, Decimal]] = {}
        self._lock = threading.RLock()
        
    def save(self, budget: RiskBudget) -> None:
        with self._lock:
            self._budgets[budget.budget_id] = budget
            
    def get(self, budget_id: str) -> Optional[RiskBudget]:
        with self._lock:
            return self._budgets.get(budget_id)
            
    def get_snapshot(self, budget_id: str) -> Optional[RiskBudgetSnapshot]:
        with self._lock:
            budget = self._budgets.get(budget_id)
            if not budget:
                return None
            return RiskBudgetSnapshot(
                budget_id=budget.budget_id,
                total_capacity=budget.total_capacity,
                utilized_capacity=budget.utilized_capacity
            )
            
    def allocate(self, request: AllocationRequest) -> Tuple[AllocationResult, Optional[RiskBudget], list[Decimal]]:
        """Atomically evaluates and applies an allocation request."""
        with self._lock:
            budget = self._budgets.get(request.budget_id)
            if not budget:
                return AllocationResult(
                    success=False,
                    amount_allocated=Decimal('0'),
                    budget_id=request.budget_id,
                    allocation_id=request.allocation_id,
                    new_utilized_capacity=Decimal('0'),
                    total_capacity=Decimal('0'),
                    reason="Budget not found"
                ), budget, []
                
            remaining_capacity = budget.total_capacity - budget.utilized_capacity
            if request.requested_amount <= remaining_capacity:
                new_utilized = budget.utilized_capacity + request.requested_amount
                
                # Near-limit logic
                crossed_thresholds = []
                emitted_set = set(budget.emitted_thresholds)
                if budget.total_capacity > 0:
                    utilization = new_utilized / budget.total_capacity
                    thresholds = [Decimal('0.80'), Decimal('0.90'), Decimal('0.95')]
                    for t in thresholds:
                        if utilization >= t and t not in emitted_set:
                            crossed_thresholds.append(t)
                            emitted_set.add(t)
                            
                new_budget = RiskBudget(
                    budget_id=budget.budget_id,
                    total_capacity=budget.total_capacity,
                    utilized_capacity=new_utilized,
                    emitted_thresholds=frozenset(emitted_set)
                )
                self._budgets[budget.budget_id] = new_budget
                self._allocations[request.allocation_id] = (budget.budget_id, request.requested_amount)
                
                return AllocationResult(
                    success=True,
                    amount_allocated=request.requested_amount,
                    budget_id=request.budget_id,
                    allocation_id=request.allocation_id,
                    new_utilized_capacity=new_utilized,
                    total_capacity=new_budget.total_capacity,
                    reason="Allocated"
                ), new_budget, crossed_thresholds
            else:
                return AllocationResult(
                    success=False,
                    amount_allocated=Decimal('0'),
                    budget_id=request.budget_id,
                    allocation_id=request.allocation_id,
                    new_utilized_capacity=budget.utilized_capacity,
                    total_capacity=budget.total_capacity,
                    reason=f"Insufficient capacity. Requested: {request.requested_amount}, Remaining: {remaining_capacity}"
                ), budget, []

    def release(self, allocation_id: str) -> Tuple[bool, Optional[RiskBudget], Decimal]:
        """Atomically releases a previously granted allocation."""
        with self._lock:
            if allocation_id not in self._allocations:
                return False, None, Decimal('0')
                
            budget_id, amount = self._allocations.pop(allocation_id)
            budget = self._budgets.get(budget_id)
            if not budget:
                return False, None, amount
                
            new_utilized = max(Decimal('0'), budget.utilized_capacity - amount)
            
            # Hysteresis reset logic
            emitted_set = set(budget.emitted_thresholds)
            if budget.total_capacity > 0:
                utilization = new_utilized / budget.total_capacity
                gap = Decimal('0.05')
                # Remove threshold if utilization is below (threshold - gap)
                for t in list(emitted_set):
                    if utilization < (t - gap):
                        emitted_set.remove(t)
            
            new_budget = RiskBudget(
                budget_id=budget.budget_id,
                total_capacity=budget.total_capacity,
                utilized_capacity=new_utilized,
                emitted_thresholds=frozenset(emitted_set)
            )
            self._budgets[budget.budget_id] = new_budget
            return True, new_budget, amount
