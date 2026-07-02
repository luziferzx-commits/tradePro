import pytest
import pandas as pd
from gqos.dashboard.edge_health import (
    calc_alpha_health,
    calc_execution_health,
    calc_risk_health,
    calc_learning_health,
    calc_overall_edge_health,
    status_from_score
)

def test_alpha_health_warming_up():
    res = calc_alpha_health(pd.DataFrame())
    assert res["status"] == "WARMING_UP"
    
def test_alpha_health_normal():
    data = [
        {"outcome": "WIN", "actual_r": 2.0, "realized_pnl": 100, "pattern_pf": 2.0},
        {"outcome": "WIN", "actual_r": 1.5, "realized_pnl": 75, "pattern_pf": 2.0},
        {"outcome": "LOSS", "actual_r": -1.0, "realized_pnl": -50, "pattern_pf": 2.0},
    ]
    df = pd.DataFrame(data * 4) # 12 trades
    res = calc_alpha_health(df)
    assert res["status"] != "WARMING_UP"
    assert res["score"] is not None
    assert 0 <= res["score"] <= 100
    assert any(c in res["confidence"] for c in ["LOW", "MEDIUM", "HIGH"])

def test_exec_health_warming_up():
    res = calc_execution_health(pd.DataFrame())
    assert res["status"] == "WARMING_UP"
    
def test_exec_health_normal():
    data = [
        {"slippage_pips": 0.5, "execution_time_ms": 150},
        {"slippage_pips": 1.0, "execution_time_ms": 200},
    ]
    res = calc_execution_health(pd.DataFrame(data))
    assert res["status"] != "WARMING_UP"
    assert res["score"] is not None
    assert 0 <= res["score"] <= 100

def test_risk_health_warming_up():
    res = calc_risk_health(None)
    assert res["status"] == "WARMING_UP"
    
def test_risk_health_normal():
    account = {"balance": 10000, "equity": 10500, "margin": 500}
    pos_list = [{"risk_usd": 100}, {"risk_usd": 50}]
    res = calc_risk_health(account, pos_list)
    assert res["status"] != "WARMING_UP"
    assert res["score"] is not None
    assert 0 <= res["score"] <= 100
    assert "Open Risk" in res["metrics"]
    assert res["metrics"]["Open Risk"] == "1.5%"

def test_learning_health_warming_up():
    res = calc_learning_health(pd.DataFrame(), pd.DataFrame())
    assert res["status"] == "WARMING_UP"
    
def test_learning_health_normal():
    pat_data = [
        {"promotion_status": "LIVE_APPROVED"},
        {"promotion_status": "REJECTED"},
        {"promotion_status": "RESEARCH_VALIDATED"},
    ]
    df_pat = pd.DataFrame(pat_data)
    df_out = pd.DataFrame([{"outcome": "WIN"}] * 25)
    res = calc_learning_health(df_pat, df_out)
    assert res["status"] != "WARMING_UP"
    assert res["score"] is not None
    assert 0 <= res["score"] <= 100

def test_overall_health():
    res = calc_overall_edge_health(
        {"score": 100},
        {"score": 100},
        {"score": 100},
        {"score": 100}
    )
    assert res["score"] == 100
    assert res["status"] == "HEALTHY"
    
    # Missing learning health
    res2 = calc_overall_edge_health(
        {"score": 100}, # Alpha
        {"score": 100}, # Exec
        {"score": 50},  # Risk
        {"score": None} # Learning missing
    )
    # Weights for missing: alpha=0.35, exec=0.25, risk=0.30 -> total 0.90
    # Expected: (100 * 0.35/0.9) + (100 * 0.25/0.9) + (50 * 0.3/0.9) = 38.88 + 27.77 + 16.66 = ~83.33
    assert 83.0 <= res2["score"] <= 84.0
    
    res3 = calc_overall_edge_health({}, {}, {}, {})
    assert res3["status"] == "WARMING_UP"
