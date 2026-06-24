import glob
import os
import pandas as pd
import xgboost as xgb
from ml.dataset_builder import build_dataset
from mlops.registry import registry
from mlops.tracker import tracker
from ml.robustness import get_walk_forward_trades, calc_pf, monte_carlo_simulation

def run_nightly_retrain():
    print("1. Rebuilding Dataset...")
    build_dataset(atr_multiplier=2.0)
    
    # Find latest dataset
    datasets = glob.glob("datasets/ml_volatility_expansion_atr_2_0_v*.csv")
    if not datasets:
        print("No datasets found.")
        return
        
    latest_dataset = sorted(datasets)[-1]
    print(f"2. Using latest dataset: {latest_dataset}")
    
    df = pd.read_csv(latest_dataset)
    features = [
        "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
    ]
    
    X = df[features]
    y = df['label']
    
    pos_count = sum(y)
    neg_count = len(y) - pos_count
    scale_weight = neg_count / pos_count if pos_count > 0 else 1.0
    
    config = {
        'max_depth': 2, 'learning_rate': 0.01, 'n_estimators': 100, 
        'subsample': 0.9, 'colsample_bytree': 0.9, 'reg_alpha': 0.1, 'reg_lambda': 10
    }
    
    print("3. Training New Candidate Model...")
    model = xgb.XGBClassifier(
        **config, scale_pos_weight=scale_weight, random_state=42, eval_metric='logloss', n_jobs=-1
    )
    model.fit(X, y)
    
    # Drift Stats
    continuous_features = [
        "atr", "adx", "ema50_slope", "rsi", "macd", "recent_high_20_distance", "recent_low_20_distance"
    ]
    drift_stats = {}
    for f in continuous_features:
        drift_stats[f] = {"mean": float(X[f].mean()), "std": float(X[f].std())}
        
    # Evaluate Validation Metrics
    print("4. Running Validation (Walk Forward + Monte Carlo)...")
    trades = get_walk_forward_trades(latest_dataset, 0.55, config)
    pf = calc_pf(trades['result_r']) if not trades.empty else 0.0
    mc_res = monte_carlo_simulation(trades, iterations=1000) if not trades.empty else pd.DataFrame()
    med_mc_pf = mc_res['pf'].median() if not mc_res.empty else 0.0
    p95_mc_dd = mc_res['max_dd'].quantile(0.95) if not mc_res.empty else 0.0
    
    metrics = {
        "pf": pf,
        "med_mc_pf": med_mc_pf,
        "p95_mc_dd": p95_mc_dd
    }
    
    metadata = {
        "description": "Nightly Retrain Candidate",
        "dataset": os.path.basename(latest_dataset),
        "features": features,
        "config": config,
        "metrics": metrics,
        "drift_stats": drift_stats
    }
    
    # 5. Log Experiment
    tracker.log_experiment("Nightly Retrain", "XGBoost", config, metrics, os.path.basename(latest_dataset))
    
    # 6. Register as Candidate
    version = registry.register_model(model, metadata, status="candidate")
    print(f"7. Model Registered as Candidate: {version}")
    
    # Auto-promote to validation if it passes baseline rules
    if med_mc_pf > 1.2 and p95_mc_dd < 15.0:
        registry.promote_model(version, "candidate", "validation")
        print(f"Model auto-promoted to Validation (MC PF: {med_mc_pf:.3f})")

if __name__ == "__main__":
    run_nightly_retrain()
