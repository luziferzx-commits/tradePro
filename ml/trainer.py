import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib
import os
import json

def calculate_metrics(y_true, y_pred, results_r):
    trades = []
    for pred, r in zip(y_pred, results_r):
        if pred == 1:
            trades.append(r)
            
    if not trades:
        return {"trades": 0, "pf": 0, "max_dd_r": 0, "net_r": 0, "precision": 0, "recall": 0, "accuracy": 0}
        
    wins = [r for r in trades if r > 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum([r for r in trades if r <= 0]))
    
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    cum_r = 0
    peak = 0
    max_dd = 0
    for r in trades:
        cum_r += r
        if cum_r > peak:
            peak = cum_r
        dd = peak - cum_r
        if dd > max_dd:
            max_dd = dd
            
    return {
        "trades": len(trades),
        "pf": round(pf, 3),
        "max_dd_r": round(max_dd, 2),
        "net_r": round(cum_r, 2),
        "precision": round(precision_score(y_true, y_pred, zero_division=0) * 100, 2),
        "recall": round(recall_score(y_true, y_pred, zero_division=0) * 100, 2),
        "accuracy": round(accuracy_score(y_true, y_pred) * 100, 2)
    }

def train_model():
    df = pd.read_csv("datasets/ml_volatility_expansion.csv")
    print(f"Loaded dataset with {len(df)} candidates.")
    
    features = [
        "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
    ]
    
    X = df[features]
    y = df['label']
    results_r = df['result_r']
    
    split_idx = int(len(df) * 0.7)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    r_train, r_test = results_r.iloc[:split_idx], results_r.iloc[split_idx:]
    
    print(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples.")
    
    pos_count = sum(y_train)
    neg_count = len(y_train) - pos_count
    scale_weight = neg_count / pos_count if pos_count > 0 else 1.0
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        scale_pos_weight=scale_weight,
        random_state=42,
        eval_metric='logloss'
    )
    
    model.fit(X_train, y_train)
    
    importances = model.feature_importances_
    fi_df = pd.DataFrame({'Feature': features, 'Importance': importances})
    fi_df = fi_df.sort_values(by='Importance', ascending=False)
    print("\n--- Feature Importance ---")
    print(fi_df.to_string(index=False))
    
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    print("\n--- Threshold Tests on 30% Out-of-Sample ---")
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70]
    
    best_candidate = None
    best_score = -1
    
    for t in thresholds:
        y_pred = (y_pred_proba >= t).astype(int)
        metrics = calculate_metrics(y_test, y_pred, r_test)
        
        print(f"\nThreshold: {t}")
        print(f"Trades: {metrics['trades']} | Precision: {metrics['precision']}% | Recall: {metrics['recall']}%")
        print(f"Profit Factor: {metrics['pf']} | Max DD: {metrics['max_dd_r']}R | Net R: {metrics['net_r']}R")
        
        if metrics['trades'] > 20 and metrics['pf'] > 1.3 and metrics['max_dd_r'] < 15:
            score = metrics['pf'] * metrics['trades'] / (metrics['max_dd_r'] + 1)
            if score > best_score:
                best_score = score
                best_candidate = metrics
                best_candidate['threshold'] = t
                
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/xgb_volatility_expansion.pkl")
    print("\nModel saved to models/xgb_volatility_expansion.pkl")
    
    if best_candidate:
        print(f"\nBest Model Setup Selected -> Threshold: {best_candidate['threshold']}")
        print(f"Trades: {best_candidate['trades']} | PF: {best_candidate['pf']} | Max DD: {best_candidate['max_dd_r']}R")
    else:
        print("\nNo threshold met the strict criteria (PF>1.3, Trades>20, MaxDD<15R).")

if __name__ == "__main__":
    train_model()
