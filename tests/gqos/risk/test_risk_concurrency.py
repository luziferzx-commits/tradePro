import concurrent.futures
from decimal import Decimal
from gqos.risk.models import RiskBudget, AllocationRequest
from gqos.risk.store import RiskBudgetStore

def test_concurrent_allocations_atomic():
    store = RiskBudgetStore()
    # 100 capacity
    store.save(RiskBudget(budget_id="strat_concurrent", total_capacity=Decimal('100.0'), utilized_capacity=Decimal('0.0')))
    
    # Simulate 200 threads trying to allocate 1.0 each
    def allocate_task(i):
        req = AllocationRequest(
            allocation_id=str(i),
            budget_id="strat_concurrent",
            strategy_id="strat_concurrent",
            requested_amount=Decimal('1.0')
        )
        res, _budget, _thresholds = store.allocate(req)
        return res.success

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(allocate_task, range(200)))
        
    # Exactly 100 should succeed, 100 should fail
    successes = sum(1 for r in results if r)
    assert successes == 100
    assert store.get("strat_concurrent").utilized_capacity == Decimal('100.0')

if __name__ == "__main__":
    test_concurrent_allocations_atomic()
    print("Concurrency test passed!")
