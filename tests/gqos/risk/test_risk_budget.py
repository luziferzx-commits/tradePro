import pytest
from gqos.risk.models import RiskBudget, AllocationRequest
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine

def test_allocation_success():
    store = RiskBudgetStore()
    budget = RiskBudget(budget_id="strat_1", total_capacity=1000.0, utilized_capacity=0.0)
    store.save(budget)
    
    engine = RiskBudgetEngine(store)
    
    req = AllocationRequest(budget_id="strat_1", strategy_id="strat_1", requested_amount=500.0)
    result, new_budget = engine.request_allocation(req)
    
    assert result.success is True
    assert result.amount_allocated == 500.0
    assert new_budget.utilized_capacity == 500.0
    
    # Store should be updated
    assert store.get("strat_1").utilized_capacity == 500.0

def test_allocation_denied_when_exceeds_budget():
    store = RiskBudgetStore()
    budget = RiskBudget(budget_id="strat_1", total_capacity=1000.0, utilized_capacity=800.0)
    store.save(budget)
    
    engine = RiskBudgetEngine(store)
    
    # Request 300, only 200 left
    req = AllocationRequest(budget_id="strat_1", strategy_id="strat_1", requested_amount=300.0)
    result, new_budget = engine.request_allocation(req)
    
    assert result.success is False
    assert result.amount_allocated == 0.0
    assert new_budget.utilized_capacity == 800.0 # unchanged
    assert store.get("strat_1").utilized_capacity == 800.0

def test_allocation_release():
    store = RiskBudgetStore()
    budget = RiskBudget(budget_id="strat_1", total_capacity=1000.0, utilized_capacity=800.0)
    store.save(budget)
    
    engine = RiskBudgetEngine(store)
    
    success, new_budget = engine.release_allocation("strat_1", 300.0)
    
    assert success is True
    assert new_budget.utilized_capacity == 500.0
    assert store.get("strat_1").utilized_capacity == 500.0

def test_allocation_release_below_zero():
    store = RiskBudgetStore()
    budget = RiskBudget(budget_id="strat_1", total_capacity=1000.0, utilized_capacity=100.0)
    store.save(budget)
    
    engine = RiskBudgetEngine(store)
    
    success, new_budget = engine.release_allocation("strat_1", 300.0)
    
    assert success is True
    assert new_budget.utilized_capacity == 0.0 # clamped to zero

def test_request_missing_budget():
    store = RiskBudgetStore()
    engine = RiskBudgetEngine(store)
    
    req = AllocationRequest(budget_id="strat_unknown", strategy_id="strat_unknown", requested_amount=100.0)
    result, new_budget = engine.request_allocation(req)
    
    assert result.success is False
    assert result.reason == "Budget not found"
    assert new_budget is None
