import pytest
import os
import pandas as pd
from datetime import datetime, timedelta
from gqos.dashboard.health_history import save_snapshot, get_history, evaluate_alerts, init_db

TEST_DB = "test_health_history.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    # Teardown before
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
        
    yield
    
    # Teardown after
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass

def test_empty_history():
    df = get_history(hours=24, db_path=TEST_DB)
    assert df.empty

def test_append_snapshot():
    metrics = {
        'overall_edge': 80.0,
        'alpha_health': 85.0,
        'execution_health': 90.0,
        'risk_health': 95.0,
        'learning_health': 80.0,
        'overall_status': 'HEALTHY',
        'confidence': 'HIGH'
    }
    save_snapshot(metrics, db_path=TEST_DB)
    
    df = get_history(hours=24, db_path=TEST_DB)
    assert not df.empty
    assert len(df) == 1
    assert df.iloc[0]['overall_edge'] == 80.0

def test_trigger_critical():
    metrics = {
        'overall_edge': 35.0,
        'alpha_health': 35.0,
        'execution_health': 90.0,
        'risk_health': 95.0,
        'learning_health': 80.0,
        'confidence': 'HIGH'
    }
    alerts = evaluate_alerts(metrics, db_path=TEST_DB)
    critical_alerts = [a for a in alerts if a['level'] == 'CRITICAL']
    assert len(critical_alerts) >= 1
    assert "Alpha Health < 40" in critical_alerts[0]['msg']

def test_no_false_critical_when_low_confidence():
    metrics = {
        'overall_edge': 35.0,
        'alpha_health': 35.0,
        'execution_health': 90.0,
        'risk_health': 95.0,
        'learning_health': 80.0,
        'confidence': 'LOW (10/30 trades)'
    }
    alerts = evaluate_alerts(metrics, db_path=TEST_DB)
    critical_alerts = [a for a in alerts if a['level'] == 'CRITICAL']
    watch_alerts = [a for a in alerts if a['level'] == 'WATCH']
    
    assert len(critical_alerts) == 0  # Should be downgraded to WATCH
    assert len(watch_alerts) >= 1
    assert "Alpha Health < 40" in watch_alerts[0]['msg']
    assert "confidence is LOW" in watch_alerts[0]['msg']

def test_trend_degradation_watch():
    # Insert old snapshot
    metrics_old = {
        'overall_edge': 90.0,
        'alpha_health': 90.0,
        'execution_health': 90.0,
        'risk_health': 95.0,
        'learning_health': 90.0,
        'confidence': 'HIGH'
    }
    save_snapshot(metrics_old, db_path=TEST_DB)
    
    # Evaluate new snapshot with > 15 drop
    metrics_new = {
        'overall_edge': 70.0,
        'alpha_health': 70.0,
        'execution_health': 90.0,
        'risk_health': 95.0,
        'learning_health': 90.0,
        'confidence': 'HIGH'
    }
    alerts = evaluate_alerts(metrics_new, db_path=TEST_DB)
    watch_alerts = [a for a in alerts if a['level'] == 'WATCH']
    
    assert any("Overall Edge dropped > 15 pts in 24h" in a['msg'] for a in watch_alerts)
