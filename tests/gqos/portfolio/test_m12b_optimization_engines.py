from decimal import Decimal
import importlib
import inspect
from gqos.portfolio.optimization.models import OptimizationProblem, TargetPortfolio
from gqos.portfolio.optimization.constraints import MaxWeightConstraint, SumToOneConstraint, SectorWeightConstraint
from gqos.portfolio.optimization.objectives import MinimizeVarianceObjective, MaximizeSharpeObjective, EqualRiskContributionObjective
from gqos.portfolio.optimization.engines import ScipyMeanVarianceOptimizer, ScipyRiskParityOptimizer
from gqos.portfolio.optimization.exceptions import OptimizationFailedError, ConstraintViolationError

def create_sample_problem(singular: bool = False) -> OptimizationProblem:
    expected_returns = {
        "AAPL": Decimal('0.10'),
        "MSFT": Decimal('0.08'),
        "JPM": Decimal('0.05')
    }
    
    if singular:
        # Perfectly correlated / singular matrix
        cov = {
            "AAPL": {"AAPL": Decimal('0.04'), "MSFT": Decimal('0.04'), "JPM": Decimal('0.04')},
            "MSFT": {"AAPL": Decimal('0.04'), "MSFT": Decimal('0.04'), "JPM": Decimal('0.04')},
            "JPM": {"AAPL": Decimal('0.04'), "MSFT": Decimal('0.04'), "JPM": Decimal('0.04')}
        }
    else:
        # Standard PSD matrix
        cov = {
            "AAPL": {"AAPL": Decimal('0.04'), "MSFT": Decimal('0.02'), "JPM": Decimal('0.01')},
            "MSFT": {"AAPL": Decimal('0.02'), "MSFT": Decimal('0.03'), "JPM": Decimal('0.015')},
            "JPM": {"AAPL": Decimal('0.01'), "MSFT": Decimal('0.015'), "JPM": Decimal('0.02')}
        }
        
    return OptimizationProblem(
        expected_returns=expected_returns,
        covariance_matrix=cov,
        objective_function_name="Test",
        constraint_names=[]
    )

def test_mean_variance_minimize_variance():
    prob = create_sample_problem()
    constraints = [SumToOneConstraint()]
    objective = MinimizeVarianceObjective()
    
    optimizer = ScipyMeanVarianceOptimizer()
    target = optimizer.optimize(prob, constraints, objective)
    
    # JPM has the lowest variance (0.02), so it should get a high weight to minimize overall variance
    assert target.target_weights["JPM"] > target.target_weights["AAPL"]
    
    # Sum to one constraint should be satisfied
    assert sum(target.target_weights.values()) - Decimal('1.0') < Decimal('0.001')

def test_mean_variance_maximize_sharpe():
    prob = create_sample_problem()
    constraints = [SumToOneConstraint()]
    objective = MaximizeSharpeObjective(risk_free_rate=0.0)
    
    optimizer = ScipyMeanVarianceOptimizer()
    target = optimizer.optimize(prob, constraints, objective)
    
    # AAPL has highest return (10%), it should get a higher weight compared to min variance
    assert target.target_weights["AAPL"] > Decimal('0.1')
    
    # Sum to one constraint should be satisfied
    assert abs(sum(target.target_weights.values()) - Decimal('1.0')) < Decimal('0.001')

def test_risk_parity_equal_risk_contribution():
    prob = create_sample_problem()
    constraints = [SumToOneConstraint()]
    objective = EqualRiskContributionObjective()
    
    optimizer = ScipyRiskParityOptimizer()
    target = optimizer.optimize(prob, constraints, objective)
    
    # In Risk Parity, lower volatility assets get higher weights to equalize risk
    # AAPL var=0.04, MSFT var=0.03, JPM var=0.02
    assert target.target_weights["JPM"] > target.target_weights["MSFT"] > target.target_weights["AAPL"]
    assert abs(sum(target.target_weights.values()) - Decimal('1.0')) < Decimal('0.001')

def test_constraint_mapping():
    prob = create_sample_problem()
    symbol_to_sector = {"AAPL": "Tech", "MSFT": "Tech", "JPM": "Fin"}
    
    constraints = [
        SumToOneConstraint(),
        MaxWeightConstraint(Decimal('0.4')), # No asset > 40%
        SectorWeightConstraint(Decimal('0.6'), symbol_to_sector) # Tech <= 60%
    ]
    
    objective = MinimizeVarianceObjective()
    optimizer = ScipyMeanVarianceOptimizer()
    target = optimizer.optimize(prob, constraints, objective)
    
    assert target.target_weights["AAPL"] <= Decimal('0.4001')
    assert target.target_weights["MSFT"] <= Decimal('0.4001')
    assert target.target_weights["JPM"] <= Decimal('0.4001')
    assert (target.target_weights["AAPL"] + target.target_weights["MSFT"]) <= Decimal('0.6001')
    assert abs(sum(target.target_weights.values()) - Decimal('1.0')) < Decimal('0.001')

def test_singular_covariance_regularization():
    prob = create_sample_problem(singular=True)
    constraints = [SumToOneConstraint()]
    objective = MinimizeVarianceObjective()
    
    optimizer = ScipyMeanVarianceOptimizer()
    # Should not crash, should regularize and return equal weights ideally
    target = optimizer.optimize(prob, constraints, objective)
    assert abs(sum(target.target_weights.values()) - Decimal('1.0')) < Decimal('0.001')

def test_determinism_10_runs():
    prob = create_sample_problem()
    constraints = [SumToOneConstraint()]
    objective = MinimizeVarianceObjective()
    
    optimizer = ScipyMeanVarianceOptimizer()
    
    first_target = optimizer.optimize(prob, constraints, objective)
    first_hash = first_target.calculate_hash()
    
    for _ in range(10):
        t = optimizer.optimize(prob, constraints, objective)
        assert t.calculate_hash() == first_hash

def test_solver_failure():
    prob = create_sample_problem()
    # Contradictory constraints
    constraints = [
        SumToOneConstraint(),
        MaxWeightConstraint(Decimal('0.1')) # Max total = 0.3, impossible to sum to 1
    ]
    objective = MinimizeVarianceObjective()
    optimizer = ScipyMeanVarianceOptimizer()
    
    try:
        optimizer.optimize(prob, constraints, objective)
        assert False, "Should have failed"
    except OptimizationFailedError:
        pass

def test_no_scipy_import_in_core_domain():
    # Verify that gqos.portfolio.optimization.interfaces, models, constraints have no scipy import
    modules_to_check = [
        "gqos.portfolio.optimization.interfaces",
        "gqos.portfolio.optimization.models",
        "gqos.portfolio.optimization.constraints"
    ]
    
    for mod_name in modules_to_check:
        mod = importlib.import_module(mod_name)
        source = inspect.getsource(mod)
        assert "scipy" not in source
        assert "numpy" not in source

if __name__ == "__main__":
    test_mean_variance_minimize_variance()
    test_mean_variance_maximize_sharpe()
    test_risk_parity_equal_risk_contribution()
    test_constraint_mapping()
    test_singular_covariance_regularization()
    test_determinism_10_runs()
    test_solver_failure()
    test_no_scipy_import_in_core_domain()
    print("M12B Optimization Engines tests passed!")
