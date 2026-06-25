import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score
from gqos.research.ml.validation import CombinatorialPurgedCV
import warnings
import json
import os

warnings.filterwarnings('ignore')

def run_decay_test(data_path: str, features_to_test: list):
    print("--- Running Dual-Axis Feature Decay Engine ---")
    df = pd.read_csv(data_path)
    
    n_samples = len(df)
    purge_candles = 10
    embargo_candles = 200
    
    # We use a simpler PurgedKFold or just a few CPCV paths to save time during decay testing
    # Using full CPCV for 50 lags * features is computationally heavy.
    # Let's use standard CPCV but only test lags [1, 5, 10, 20, 50]
    lags = [1, 5, 10, 20, 50]
    
    cpcv = CombinatorialPurgedCV(
        n_groups=6, k_test_groups=2, 
        purge_pct=purge_candles/n_samples, 
        embargo_pct=embargo_candles/n_samples
    )
    
    splits = list(cpcv.split(df))
    
    base_model = xgb.XGBClassifier(
        max_depth=2, learning_rate=0.01, n_estimators=100, subsample=0.9,
        random_state=42, eval_metric='logloss', n_jobs=-1
    )
    
    decay_results = {}
    
    # Pre-calculate base MDA at lag 0
    print("Calculating Base MDA (Lag 0)...")
    base_mda = {f: [] for f in features_to_test}
    for train_idx, test_idx in splits:
        X_train = df.iloc[train_idx][features_to_test]
        y_train = df.iloc[train_idx]['label']
        X_test = df.iloc[test_idx][features_to_test]
        y_test = df.iloc[test_idx]['label']
        
        if len(y_train) < 50 or len(X_test) == 0:
            continue
            
        model = xgb.XGBClassifier(**base_model.get_params())
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        base_acc = accuracy_score(y_test, preds)
        
        for col in features_to_test:
            X_permuted = X_test.copy()
            X_permuted[col] = np.random.permutation(X_permuted[col].values)
            permuted_preds = model.predict(X_permuted)
            base_mda[col].append(base_acc - accuracy_score(y_test, permuted_preds))
            
    base_mda_mean = {k: np.mean(v) for k, v in base_mda.items()}
    
    for feat in features_to_test:
        if base_mda_mean[feat] <= 0:
            print(f"Skipping {feat} (Base MDA <= 0)")
            continue
            
        print(f"\nTesting Decay for {feat}...")
        decay_curve = {0: base_mda_mean[feat]}
        
        for lag in lags:
            mda_at_lag = []
            
            # Shift feature
            df_lagged = df.copy()
            df_lagged[feat] = df_lagged[feat].shift(lag)
            # dropna for training stability
            # But to keep indices aligned with CPCV, we just fillna(0)
            df_lagged[feat] = df_lagged[feat].fillna(0)
            
            for train_idx, test_idx in splits:
                X_train = df_lagged.iloc[train_idx][features_to_test]
                y_train = df_lagged.iloc[train_idx]['label']
                X_test = df_lagged.iloc[test_idx][features_to_test]
                y_test = df_lagged.iloc[test_idx]['label']
                
                if len(y_train) < 50 or len(X_test) == 0:
                    continue
                    
                model = xgb.XGBClassifier(**base_model.get_params())
                model.fit(X_train, y_train)
                preds = model.predict(X_test)
                base_acc = accuracy_score(y_test, preds)
                
                X_permuted = X_test.copy()
                X_permuted[feat] = np.random.permutation(X_permuted[feat].values)
                permuted_preds = model.predict(X_permuted)
                mda_at_lag.append(base_acc - accuracy_score(y_test, permuted_preds))
                
            mean_mda_lag = np.mean(mda_at_lag)
            decay_curve[lag] = mean_mda_lag
            
            drop_pct = (base_mda_mean[feat] - mean_mda_lag) / base_mda_mean[feat] * 100
            print(f"  Lag {lag:2}: MDA = {mean_mda_lag:.4f} (Drop: {drop_pct:.1f}%)")
            
        # Check rule: MDA drops > 60% within 10 lags -> microstructure noise
        drop_at_10 = (base_mda_mean[feat] - decay_curve[10]) / base_mda_mean[feat]
        is_noise = drop_at_10 > 0.60
        
        if is_noise:
            print(f"  🚨 FLAG: {feat} is microstructure noise (>60% decay by lag 10)")
        
        decay_results[feat] = {
            "curve": decay_curve,
            "is_microstructure_noise": is_noise
        }
        
    os.makedirs("ml/temp", exist_ok=True)
    with open("ml/temp/decay_results.json", "w") as f:
        json.dump(decay_results, f, indent=4)
        
    return decay_results

if __name__ == "__main__":
    import glob
    files = glob.glob("datasets/*/*.csv")
    if not files:
        files = glob.glob("datasets/*.csv")
    data_file = files[-1]
    for f in files:
        if "XAUUSDm" in f:
            data_file = f
            break
            
    features = [
        "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
    ]
    df = pd.read_csv(data_file)
    features = [f for f in features if f in df.columns]
    
    run_decay_test(data_file, features)
