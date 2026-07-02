import pytest
from decimal import Decimal
from gqos.risk.models import RiskBudget, AllocationRequest
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine


def test_allocation_success():
    store = RiskBudgetStore()
    budget = RiskBudget(budget_id="strat_1", total_capacity=Decimal('1000'), utilized_capacity=Decimal('0'))
    store.save(budget)

    engine = RiskBudgetEngine(store)

    req = AllocationRequest(allocation_id="a1", budget_id="strat_1", strategy_id="strat_1", requested_amount=Decimal('500'))
    result, new_budget, _thresholds = engine.request_allocation(req)

    assert result.success is True
    assert result.amount_allocated == Decimal('500')
    assert new_budget.utilized_capacity == Decimal('500')

    # Store should be updated
    assert store.get("strat_1").utilized_capacity == Decimal('500')


def test_allocation_denied_when_exceeds_budget():
    store = RiskBudgetStore()
    budget = RiskBudget(budget_id="strat_1", total_capacity=Decimal('1000'), utilized_capacity=Decimal('800'))
    store.save(budget)

    engine = RiskBudgetEngine(store)

    # Request 300, only 200 left
    req = AllocationRequest(allocation_id="a1", budget_id="strat_1", strategy_id="strat_1", requested_amount=Decimal('300'))
    result, new_budget, _thresholds = engine.request_allocation(req)

    assert result.success is False
    assert result.amount_allocated == Decimal('0')
    assert new_budget.utilized_capacity == Decimal('800')  # unchanged
    assert store.get("strat_1").utilized_capacity == Decimal('800')


def test_allocation_release():
    store = RiskBudgetStore()
    budget = RiskBudget(budget_id="strat_1", total_capacity=Decimal('1000'), utilized_capacity=Decimal('0'))
    store.save(budget)

    engine = RiskBudgetEngine(store)

    # Allocate first so there is an allocation_id to release.
    req = AllocationRequest(allocation_id="a1", budget_id="strat_1", strategy_id="strat_1", requested_amount=Decimal('300'))
    engine.request_allocation(req)
    assert store.get("strat_1").utilized_capacity == Decimal('300')

    success, new_budget, amount = engine.release_allocation("a1")

    assert success is True
    assert amount == Decimal('300')
    assert new_budget.utilized_capacity == Decimal('0')
    assert store.get("strat_1").utilized_capacity == Decimal('0')


def test_allocation_release_clamps_to_zero():
    store = RiskBudgetStore()
    budget = RiskBudget(budget_id="strat_1", total_capacity=Decimal('1000'), utilized_capacity=Decimal('100'))
    store.save(budget)

    # Seed an inconsistent allocation whose amount exceeds current utilization
    # to verify utilized capacity never goes negative.
    store._allocations["a1"] = ("strat_1", Decimal('300'))

    engine = RiskBudgetEngine(store)
    success, new_budget, _amount = engine.release_allocation("a1")

    assert success is True
    assert new_budget.utilized_capacity == Decimal('0')  # clamped to zero


def test_release_unknown_allocation():
    store = RiskBudgetStore()
    engine = RiskBudgetEngine(store)

    success, new_budget, amount = engine.release_allocation("does-not-exist")
    assert success is False
    assert new_budget is None
    assert amount == Decimal('0')


def test_request_missing_budget():
    store = RiskBudgetStore()
    engine = RiskBudgetEngine(store)

    req = AllocationRequest(allocation_id="a1", budget_id="strat_unknown", strategy_id="strat_unknown", requested_amount=Decimal('100'))
    result, new_budget, _thresholds = engine.request_allocation(req)

    assert result.success is False
    assert result.reason == "Budget not found"
    assert new_budget is None
