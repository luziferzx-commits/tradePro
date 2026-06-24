import pandas as pd
import xgboost as xgb
from mlops.registry import registry
import json

def train_and_register_candidate(symbol="XAUUSDm", dataset_path="datasets/XAUUSDm/XAUUSDm_dataset_atr_2_0_v001.csv"):
    print(f"--- Training Final Candidate Model for {symbol} ---")
    df = pd.read_csv(dataset_path)
    
    # Use normalized features for Multi-Market setup
    features = [
        "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "atr_pct", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance",
        "recent_high_20_distance_pct", "recent_low_20_distance_pct"
    ]
    
    X = df[features]
    y = df['label']
    
    # Selected by user: SPW 1.10
    scale_weight = 1.10
    
    config = {
        'max_depth': 4, 
        'learning_rate': 0.01, 
        'n_estimators': 300, 
        'subsample': 0.8, 
        'colsample_bytree': 0.8, 
        'scale_pos_weight': scale_weight
    }
    
    model = xgb.XGBClassifier(
        **config,
        random_state=42,
        eval_metric='logloss',
        n_jobs=-1
    )
    
    model.fit(X, y)
    
    continuous_features = [f for f in features if f not in ["is_high_volatility", "is_buy", "hour_utc"]]
    
    drift_stats = {}
    for f in continuous_features:
        drift_stats[f] = {
            "mean": float(X[f].mean()),
            "std": float(X[f].std())
        }
    
    metadata = {
        "description": f"{symbol} Candidate Forward Dry Run Model",
        "dataset": dataset_path,
        "features": features,
        "config": config,
        "drift_stats": drift_stats,
        "min_confidence_expected": 0.515
    }
    
    version = registry.register_model(model, metadata, status="candidate", symbol=symbol)
    print(f"Model successfully registered in CANDIDATE as {version} for {symbol}!")
    return version

if __name__ == "__main__":
    train_and_register_candidate()
