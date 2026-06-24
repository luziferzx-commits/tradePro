from decimal import Decimal
from typing import List, Dict
import copy

from gqos.portfolio.optimization.models import OptimizationProblem, TargetPortfolio
from gqos.portfolio.optimization.interfaces import IObjectiveFunction, IConstraint, IOptimizer
from gqos.portfolio.optimization.constraints import MaxWeightConstraint, SumToOneConstraint
from gqos.portfolio.optimization.objectives import MinimizeVarianceObjective
from gqos.portfolio.optimization.engines import ScipyMeanVarianceOptimizer
from gqos.portfolio.optimization.analytics.sensitivity import SensitivityAnalyzer
from gqos.portfolio.optimization.analytics.regression import OptimizerRegressionHarness
from gqos.portfolio.optimization.analytics.exceptions import RegressionDriftDetectedError

def create_sample_problem() -> OptimizationProblem:
    expected_returns = {
        "AAPL": Decimal('0.10'),
        "MSFT": Decimal('0.08'),
        "JPM": Decimal('0.05')
    }
    
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

def test_sensitivity_analyzer():
    optimizer = ScipyMeanVarianceOptimizer()
    analyzer = SensitivityAnalyzer(optimizer)
    
    problem = create_sample_problem()
    constraints = [SumToOneConstraint()]
    objective = MinimizeVarianceObjective()
    
    # Perturb AAPL by +10% relative to its return
    def perturb_func(sym: str, ret: Decimal) -> Decimal:
        if sym == "AAPL":
            return ret * Decimal('1.1')
        return ret
        
    result = analyzer.analyze_returns_sensitivity(problem, constraints, objective, perturb_func)
    
    # Result should be immutable
    assert hasattr(result, "total_turnover")
    assert result.original_portfolio_hash == result.perturbed_portfolio_hash
    
    # Weight drift calculation
    assert "AAPL" in result.weight_drift_by_symbol
    
    # Since MinimizeVariance doesn't use expected_returns (it only looks at Covariance),
    # the weights should actually be IDENTICAL if we only perturbed returns!
    # Let's verify turnover is 0 for MinimizeVariance.
    assert result.total_turnover == Decimal('0')
    
    # Now let's try MaximizeSharpe which DOES use expected returns
    from gqos.portfolio.optimization.objectives import MaximizeSharpeObjective
    objective_sharpe = MaximizeSharpeObjective()
    
    result_sharpe = analyzer.analyze_returns_sensitivity(problem, constraints, objective_sharpe, perturb_func)
    
    # Turnover should be > 0 because expected return changed
    assert result_sharpe.total_turnover > Decimal('0')
    
    # Original problem must be unchanged (immutable dataclass)
    assert problem.expected_returns["AAPL"] == Decimal('0.10')

def test_regression_baseline_and_drift_detection():
    optimizer = ScipyMeanVarianceOptimizer()
    harness = OptimizerRegressionHarness(optimizer)
    
    problem = create_sample_problem()
    constraints = [SumToOneConstraint()]
    objective = MinimizeVarianceObjective()
    
    # First, let's get the true hash
    portfolio = optimizer.optimize(problem, constraints, objective)
    true_hash = portfolio.calculate_hash()
    
    # Test 1: Successful regression match
    matched_portfolio = harness.assert_regression_baseline(problem, constraints, objective, true_hash)
    assert matched_portfolio.calculate_hash() == true_hash
    
    # Test 2: Drift detection (simulated by passing wrong expected hash)
    fake_hash = "abc123wronghash"
    try:
        harness.assert_regression_baseline(problem, constraints, objective, fake_hash)
        assert False, "Should have raised RegressionDriftDetectedError"
    except RegressionDriftDetectedError as e:
        assert e.expected_hash == fake_hash
        assert e.actual_hash == true_hash

def test_deterministic_100_run_replay():
    optimizer = ScipyMeanVarianceOptimizer()
    harness = OptimizerRegressionHarness(optimizer)
    
    problem = create_sample_problem()
    constraints = [SumToOneConstraint()]
    objective = MinimizeVarianceObjective()
    
    # Get initial
    true_hash = optimizer.optimize(problem, constraints, objective).calculate_hash()
    
    # 100 Run Replay to ensure no stochastic drift
    for _ in range(100):
        harness.assert_regression_baseline(problem, constraints, objective, true_hash)

if __name__ == "__main__":
    test_sensitivity_analyzer()
    test_regression_baseline_and_drift_detection()
    test_deterministic_100_run_replay()
    print("M12C Analytics tests passed!")
