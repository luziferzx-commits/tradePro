import pytest
import os
import pandas as pd
import numpy as np

from gqos.research.hypothesis import IHypothesis
from gqos.research.experiment import ExperimentTracker, DatasetVersion
from gqos.research.statistics.benchmark import BenchmarkEngine
from gqos.research.statistics.edge import InstitutionalEdgeScore
from gqos.research.archive.store import SQLiteResearchStore
from gqos.research.analytics import FailureAnalytics
from gqos.research.genealogy import FeatureGenealogy
from gqos.research.notebook import ResearchNotebookGenerator

def test_benchmark_superiority():
    # Market makes 0 returns
    market = pd.Series(np.zeros(252))
    # Alpha makes 1% consistent return
    alpha = pd.Series(np.full(252, 0.01))
    
    metrics = BenchmarkEngine.evaluate_alpha(alpha, market)
    
    assert metrics["excess_return_ann"] > 0
    assert metrics["tracking_error_ann"] == 0 # Since it's exactly 0.01 every day, std deviation is 0
    assert metrics["information_ratio"] == 0.0 # Division by 0 tracking error handles correctly

def test_feature_genealogy_integrity():
    fg = FeatureGenealogy()
    fg.register_alpha("Alpha1", ["RSI_14", "MACD"])
    fg.register_alpha("Alpha2", ["RSI_14", "ATR"])
    
    impacted = fg.get_impacted_alphas("RSI_14")
    assert "Alpha1" in impacted
    assert "Alpha2" in impacted
    
    impacted_macd = fg.get_impacted_alphas("MACD")
    assert "Alpha1" in impacted_macd
    assert "Alpha2" not in impacted_macd

def test_research_archive_replay():
    store = SQLiteResearchStore(":memory:")
    
    alpha_record = {
        "alpha_id": "A100",
        "category": "Champion",
        "metrics": {"sharpe": 2.5, "pbo": 0.05},
        "edge_score": 85.0
    }
    
    store.save_alpha(alpha_record)
    
    retrieved = store.get_alpha("A100")
    assert retrieved is not None
    assert retrieved["alpha_id"] == "A100"
    assert retrieved["category"] == "Champion"

def test_leaderboard_consistency():
    store = SQLiteResearchStore(":memory:")
    store.save_alpha({"alpha_id": "A1", "edge_score": 50.0})
    store.save_alpha({"alpha_id": "A2", "edge_score": 90.0})
    store.save_alpha({"alpha_id": "A3", "edge_score": 10.0})
    
    leaderboard = store.get_leaderboard(metric="edge_score", top_n=2)
    assert len(leaderboard) == 2
    assert leaderboard[0]["alpha_id"] == "A2"
    assert leaderboard[1]["alpha_id"] == "A1"

def test_experiment_reproducibility_tracker():
    tracker = ExperimentTracker("EXP-1")
    tracker.start_run("RUN-1")
    cost = tracker.end_run()
    
    assert cost.cpu_time_seconds >= 0
    assert cost.peak_ram_mb > 0

if __name__ == "__main__":
    pytest.main(["-v", __file__])
