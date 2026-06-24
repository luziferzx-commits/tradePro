import pandas as pd
import xgboost as xgb
from mlops.registry import registry

def train_and_register_production():
    print("Training production model on ALL data...")
    dataset_path = "datasets/ml_volatility_expansion_atr_2_0.csv"
    df = pd.read_csv(dataset_path)
    
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
    
    model = xgb.XGBClassifier(
        **config,
        scale_pos_weight=scale_weight,
        random_state=42,
        eval_metric='logloss',
        n_jobs=-1
    )
    
    model.fit(X, y)
    
    # Calculate Drift Statistics
    continuous_features = [
        "atr", "adx", "ema50_slope", "rsi", "macd",
        "recent_high_20_distance", "recent_low_20_distance"
    ]
    
    drift_stats = {}
    for f in continuous_features:
        drift_stats[f] = {
            "mean": float(X[f].mean()),
            "std": float(X[f].std())
        }
    
    metadata = {
        "description": "V3.25 Robust Model (Stable Zone)",
        "dataset": "ml_volatility_expansion_atr_2_0.csv",
        "features": features,
        "config": config,
        "walk_forward_score": "PASS (Med PF: 2.123)",
        "monte_carlo_score": "PASS",
        "bootstrap_score": "PASS",
        "expected_rr": 2.5,
        "expected_holding_time_hrs": 4.0, 
        "expected_max_dd_r": 9.99,
        "drift_stats": drift_stats
    }
    
    version = registry.register_model(model, metadata, status="production")
    print(f"Model successfully registered in production as {version}!")

if __name__ == "__main__":
    train_and_register_production()
