from decimal import Decimal
from typing import List
from gqos.portfolio.optimization.models import OptimizationProblem, TargetPortfolio
from gqos.portfolio.optimization.interfaces import IObjectiveFunction, IConstraint, IOptimizer
from gqos.portfolio.optimization.constraints import MaxWeightConstraint, SumToOneConstraint, SectorWeightConstraint

class DummyObjective(IObjectiveFunction):
    @property
    def name(self) -> str:
        return "DummyObjective"

class DummyOptimizer(IOptimizer):
    def optimize(self, problem: OptimizationProblem, constraints: List[IConstraint], objective: IObjectiveFunction) -> TargetPortfolio:
        # Stateless dummy implementation: Equal weight
        n = len(problem.expected_returns)
        if n == 0:
            return TargetPortfolio({})
        weight = Decimal('1.0') / Decimal(n)
        target_weights = {symbol: weight for symbol in problem.expected_returns.keys()}
        return TargetPortfolio(target_weights)

def test_models_hashable_and_immutable():
    # OptimizationProblem Hash
    prob1 = OptimizationProblem(
        expected_returns={"AAPL": Decimal('0.10'), "MSFT": Decimal('0.08')},
        covariance_matrix={
            "AAPL": {"AAPL": Decimal('0.04'), "MSFT": Decimal('0.02')},
            "MSFT": {"AAPL": Decimal('0.02'), "MSFT": Decimal('0.03')}
        },
        objective_function_name="DummyObjective",
        constraint_names=["MaxWeightConstraint(0.5)"]
    )
    
    # Same data, different order
    prob2 = OptimizationProblem(
        expected_returns={"MSFT": Decimal('0.08'), "AAPL": Decimal('0.10')},
        covariance_matrix={
            "MSFT": {"MSFT": Decimal('0.03'), "AAPL": Decimal('0.02')},
            "AAPL": {"MSFT": Decimal('0.02'), "AAPL": Decimal('0.04')}
        },
        objective_function_name="DummyObjective",
        constraint_names=["MaxWeightConstraint(0.5)"]
    )
    
    assert prob1.calculate_hash() == prob2.calculate_hash()
    
    # TargetPortfolio Hash
    tp1 = TargetPortfolio({"AAPL": Decimal('0.6'), "MSFT": Decimal('0.4')})
    tp2 = TargetPortfolio({"MSFT": Decimal('0.4'), "AAPL": Decimal('0.6')})
    assert tp1.calculate_hash() == tp2.calculate_hash()

def test_max_weight_constraint():
    constraint = MaxWeightConstraint(Decimal('0.5'))
    
    # Valid
    tp_valid = TargetPortfolio({"AAPL": Decimal('0.5'), "MSFT": Decimal('0.5')})
    res_valid = constraint.validate(tp_valid)
    assert res_valid.is_valid
    
    # Invalid
    tp_invalid = TargetPortfolio({"AAPL": Decimal('0.6'), "MSFT": Decimal('0.4')})
    res_invalid = constraint.validate(tp_invalid)
    assert not res_invalid.is_valid
    assert len(res_invalid.violations) == 1
    assert "AAPL" in res_invalid.violations[0]

def test_sum_to_one_constraint():
    constraint = SumToOneConstraint(tolerance=Decimal('0.001'))
    
    # Valid
    tp_valid = TargetPortfolio({"AAPL": Decimal('0.5005'), "MSFT": Decimal('0.4995')}) # Sum = 1.0
    assert constraint.validate(tp_valid).is_valid
    
    # Valid within tolerance
    tp_valid_tol = TargetPortfolio({"AAPL": Decimal('0.5'), "MSFT": Decimal('0.5005')}) # Sum = 1.0005
    assert constraint.validate(tp_valid_tol).is_valid
    
    # Invalid
    tp_invalid = TargetPortfolio({"AAPL": Decimal('0.5'), "MSFT": Decimal('0.51')}) # Sum = 1.01
    res = constraint.validate(tp_invalid)
    assert not res.is_valid
    assert len(res.violations) == 1

def test_sector_weight_constraint():
    symbol_to_sector = {"AAPL": "Tech", "MSFT": "Tech", "JPM": "Financials"}
    constraint = SectorWeightConstraint(max_sector_weight=Decimal('0.6'), symbol_to_sector=symbol_to_sector)
    
    # Valid: Tech = 0.5, Fin = 0.5
    tp_valid = TargetPortfolio({"AAPL": Decimal('0.25'), "MSFT": Decimal('0.25'), "JPM": Decimal('0.5')})
    assert constraint.validate(tp_valid).is_valid
    
    # Invalid: Tech = 0.7 > 0.6
    tp_invalid = TargetPortfolio({"AAPL": Decimal('0.4'), "MSFT": Decimal('0.3'), "JPM": Decimal('0.3')})
    res = constraint.validate(tp_invalid)
    assert not res.is_valid
    assert "Tech" in res.violations[0]

def test_ioptimizer_contract():
    prob = OptimizationProblem(
        expected_returns={"AAPL": Decimal('0.10'), "MSFT": Decimal('0.08')},
        covariance_matrix={},
        objective_function_name="DummyObjective",
        constraint_names=[]
    )
    
    optimizer = DummyOptimizer()
    target = optimizer.optimize(prob, [], DummyObjective())
    
    # Should be equally weighted
    assert target.target_weights["AAPL"] == Decimal('0.5')
    assert target.target_weights["MSFT"] == Decimal('0.5')
    
    # Prove stateless by running again
    target2 = optimizer.optimize(prob, [], DummyObjective())
    assert target.calculate_hash() == target2.calculate_hash()

if __name__ == "__main__":
    test_models_hashable_and_immutable()
    test_max_weight_constraint()
    test_sum_to_one_constraint()
    test_sector_weight_constraint()
    test_ioptimizer_contract()
    print("M12A Optimization Core tests passed!")
