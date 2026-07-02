import pandas as pd
import xgboost as xgb
from mlops.registry import registry

def train_and_register_production(symbol="XAUUSDm", dataset_path="datasets/ml_volatility_expansion_atr_2_0.csv", status="candidate"):
    print(f"Training {status} model on ALL data for {symbol}...")
    df = pd.read_csv(dataset_path)
    
    # Use normalized features
    features = [
        "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr_pct", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance_pct", "recent_low_20_distance_pct"
    ]
    
    # Backward compatibility: if the dataset doesn't have the new pct features, fallback to old ones
    if "atr_pct" not in df.columns:
        features = [
            "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
            "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
            "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
        ]
        
    X = df[features]
    y = df['label']
    
    # Walk-Forward: 80/20 temporal split
    split_idx = int(len(df) * 0.8)
    X_train, y_train = X.iloc[:split_idx], y.iloc[:split_idx]
    X_test, y_test = X.iloc[split_idx:], y.iloc[split_idx:]
    
    pos_count = sum(y_train)
    neg_count = len(y_train) - pos_count
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
    
    model.fit(X_train, y_train)
    
    # OOS Evaluation
    preds = model.predict(X_test)
    wins = sum((preds == 1) & (y_test == 1))
    losses = sum((preds == 1) & (y_test == 0))
    oos_pf = (wins * 2.0) / losses if losses > 0 else (wins * 2.0)
    print(f"OOS Evaluation: {wins}W {losses}L, PF: {oos_pf:.2f}")
    
    # Fetch Old Model PF
    old_model, old_meta = registry.get_production_model(symbol)
    old_pf = old_meta.get("oos_pf", 0.0) if old_meta else 0.0
    
    # Rollback Logic
    if old_model and oos_pf < old_pf * 0.90:
        print(f"ROLLBACK: New OOS PF ({oos_pf:.2f}) < 90% of Old PF ({old_pf:.2f}). Rejecting new model.")
        registry.register_model(model, {"oos_pf": float(oos_pf)}, status="archive", symbol=symbol)
        return old_meta.get("model_version", "unknown")
        
    continuous_features = [f for f in features if f not in ["is_high_volatility", "is_buy", "hour_utc"]]
    
    drift_stats = {}
    for f in continuous_features:
        drift_stats[f] = {
            "mean": float(X_train[f].mean()),
            "std": float(X_train[f].std())
        }
    
    metadata = {
        "description": f"Multi-Market {symbol} Model",
        "dataset": dataset_path,
        "features": features,
        "config": config,
        "drift_stats": drift_stats,
        "oos_pf": float(oos_pf)
    }
    
    version = registry.register_model(model, metadata, status=status, symbol=symbol)
    print(f"Model successfully registered in {status} as {version} for {symbol} (OOS PF: {oos_pf:.2f})!")
    return version

if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "XAUUSDm"
    dataset_path = sys.argv[2] if len(sys.argv) > 2 else "datasets/ml_volatility_expansion_atr_2_0.csv"
    status = sys.argv[3] if len(sys.argv) > 3 else "candidate"
    train_and_register_production(symbol, dataset_path, status)
