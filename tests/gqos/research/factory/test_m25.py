import pytest
import numpy as np
import pandas as pd

from gqos.alpha.models import AlphaMetadata
from gqos.research.factory.generators import StrategyGenerator
from gqos.research.factory.constraints import ConstraintEngine, TurnoverConstraint, LiquidityConstraint, CapacityConstraint
from gqos.research.factory.evaluator import VectorizedEvaluator, DeflatedSharpeRatio
from gqos.research.factory.tournament import AlphaTournament, CorrelationFilter
from gqos.research.ml.registry import ChampionChallengerRegistry

@pytest.fixture
def base_metadata():
    return AlphaMetadata(
        long_only=False, supports_short=True, supports_leverage=True,
        capacity="100M", estimated_capacity=100000000.0, adv_percentage=0.1,
        liquidity_requirement="Top 100", expected_holding_period="1d",
        asset_class="equity", frequency="daily", turnover="high",
        expected_market=["bull"], stability_score=0.0, tags=[]
    )

def test_template_generator_deterministic_hash(base_metadata):
    param_grid = {
        "lookback": [5, 10, 20],
        "threshold": [1.0, 2.0]
    }
    
    alphas = StrategyGenerator.generate_from_grid("MeanReversion", param_grid, base_metadata)
    
    assert len(alphas) == 6
    # Deterministic hash test
    alpha_1 = alphas[0]
    
    # Re-generate identically
    alphas_2 = StrategyGenerator.generate_from_grid("MeanReversion", {"lookback": [5], "threshold": [1.0]}, base_metadata)
    assert alpha_1.alpha_id == alphas_2[0].alpha_id
    
    # Metadata includes parameter tags
    tags = alpha_1.metadata.tags
    assert any("template:MeanReversion" in tag for tag in tags)

def test_constraint_engine(base_metadata):
    alphas = StrategyGenerator.generate_from_grid("Test", {"a": [1]}, base_metadata)
    alpha = alphas[0]
    
    engine = ConstraintEngine()
    engine.add_constraint(TurnoverConstraint(max_annual_turnover=100.0))
    engine.add_constraint(CapacityConstraint(min_capacity=50000000.0))
    
    metrics = {"annual_turnover": 150.0} # Fails turnover
    
    survivors = engine.filter([alpha], {alpha.alpha_id: metrics})
    assert len(survivors) == 0
    
    metrics_pass = {"annual_turnover": 50.0} # Passes
    survivors = engine.filter([alpha], {alpha.alpha_id: metrics_pass})
    assert len(survivors) == 1

def test_vectorized_evaluator():
    np.random.seed(42)
    # 252 days of random prices
    returns = np.random.normal(0.001, 0.02, 252)
    prices = pd.Series((1 + returns).cumprod())
    
    evaluator = VectorizedEvaluator(prices)
    
    # Perfect foresight signal
    signals = pd.Series(np.sign(evaluator.returns))
    metrics = evaluator.evaluate(signals)
    
    assert metrics["sharpe"] > 0
    assert metrics["sample_size"] == 251 # length minus 1 due to shift
    
def test_deflated_sharpe_ratio():
    trial_sharpes = [0.1, 0.5, 0.2, 0.8, -0.1, 1.2, 0.4]
    
    # Single trial with high sharpe
    dsr = DeflatedSharpeRatio.calculate(1.5, trial_sharpes, skew=0.0, kurtosis=3.0, sample_size=252)
    assert dsr > 0.5 # Should be likely true
    
    # Large number of trials deflates the score
    many_trials = list(np.random.normal(0, 1, 10000))
    dsr_deflated = DeflatedSharpeRatio.calculate(1.5, many_trials, skew=0.0, kurtosis=3.0, sample_size=252)
    
    # The DSR should be heavily penalized
    assert dsr_deflated < dsr

def test_tournament_and_correlation(base_metadata):
    np.random.seed(42)
    prices = pd.Series((1 + np.random.normal(0.001, 0.02, 252)).cumprod())
    evaluator = VectorizedEvaluator(prices)
    registry = ChampionChallengerRegistry()
    
    tournament = AlphaTournament(evaluator, registry)
    
    # Generate 10 dummy alphas
    alphas = StrategyGenerator.generate_from_grid("Test", {"idx": list(range(10))}, base_metadata)
    
    def dummy_signal_gen(alpha):
        # Generate random signals. If idx is even, highly correlated with another even.
        if alpha.parameters["idx"] % 2 == 0:
            return pd.Series(np.ones(252)) # Highly correlated (identical)
        return pd.Series(np.random.choice([-1, 1], size=252))
        
    winners = tournament.run_tournament(alphas, dummy_signal_gen, max_correlation=0.5, top_n=3)
    
    # Should not have all even index strategies due to correlation filter
    even_count = sum(1 for a in winners if a.parameters["idx"] % 2 == 0)
    assert even_count <= 1
    
    assert len(winners) <= 3
    
    # Check registration
    assert len(registry.challengers) == len(winners)
    assert len(registry.champions) == 0 # NO live promotion

if __name__ == "__main__":
    pytest.main(["-v", __file__])
