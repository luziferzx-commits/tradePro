import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score, precision_score, recall_score
import os
from datetime import datetime

def calculate_metrics(y_true, y_pred, results_r):
    trades = []
    for pred, r in zip(y_pred, results_r):
        if pred == 1:
            trades.append(r)
            
    if not trades:
        return {"trades": 0, "pf": 0.0, "max_dd_r": 0.0, "net_r": 0.0, "precision": 0.0, "recall": 0.0, "accuracy": 0.0}
        
    wins = [r for r in trades if r > 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum([r for r in trades if r <= 0]))
    
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    if pf == float('inf') and gross_profit > 0:
        pf = 99.9  # Cap infinity for realistic averaging
    elif pf == float('inf'):
        pf = 0.0
        
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

def run_walk_forward():
    print("Loading dataset...")
    df = pd.read_csv("datasets/ml_volatility_expansion.csv")
    df['datetime'] = pd.to_datetime(df['timestamp'])
    df['month'] = df['datetime'].dt.to_period('M')
    
    months = sorted(df['month'].unique())
    print(f"Total months available: {len(months)} -> {[str(m) for m in months]}")
    
    if len(months) < 4:
        print("Not enough months for Walk-Forward Validation (Train 3, Test 1 requires at least 4 months).")
        return
        
    features = [
        "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
    ]
    
    thresholds = [0.50, 0.55, 0.60, 0.65]
    all_results = []
    
    for i in range(len(months) - 3):
        train_months = months[i:i+3]
        test_month = months[i+3]
        
        print(f"\n--- Fold {i+1} ---")
        print(f"Train: {[str(m) for m in train_months]} | Test: {test_month}")
        
        train_mask = df['month'].isin(train_months)
        test_mask = df['month'] == test_month
        
        X_train = df[train_mask][features]
        y_train = df[train_mask]['label']
        
        X_test = df[test_mask][features]
        y_test = df[test_mask]['label']
        r_test = df[test_mask]['result_r']
        
        if len(y_train) == 0 or len(y_test) == 0:
            print("Skipping due to empty train/test split.")
            continue
            
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
        
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        
        for t in thresholds:
            y_pred = (y_pred_proba >= t).astype(int)
            metrics = calculate_metrics(y_test, y_pred, r_test)
            
            res = {
                "fold": i+1,
                "train_months": f"{train_months[0]} to {train_months[-1]}",
                "test_month": str(test_month),
                "threshold": t,
                "trades": metrics['trades'],
                "win_rate_pct": metrics['precision'],
                "profit_factor": metrics['pf'],
                "max_dd_r": metrics['max_dd_r'],
                "expectancy_r": round(metrics['net_r'] / metrics['trades'], 3) if metrics['trades'] > 0 else 0,
                "net_r": metrics['net_r']
            }
            all_results.append(res)
            
    results_df = pd.DataFrame(all_results)
    os.makedirs("ml/reports", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_file = f"ml/reports/walk_forward_xgb_{today}.csv"
    results_df.to_csv(out_file, index=False)
    print(f"\nWalk-forward report saved to {out_file}")
    
    # Acceptance Criteria Evaluation
    print("\n=== Acceptance Criteria Verification ===")
    
    for t in thresholds:
        print(f"\n--- Evaluation for Threshold {t} ---")
        t_df = results_df[results_df['threshold'] == t]
        
        num_folds = len(t_df)
        avg_pf = t_df['profit_factor'].mean()
        median_pf = t_df['profit_factor'].median()
        max_dd = t_df['max_dd_r'].max()
        pct_pf_gt_1 = (len(t_df[t_df['profit_factor'] > 1.0]) / num_folds) * 100
        pct_pf_gt_13 = (len(t_df[t_df['profit_factor'] > 1.3]) / num_folds) * 100
        
        crit_1 = avg_pf > 1.3
        crit_2 = median_pf > 1.2
        crit_3 = max_dd < 15.0
        crit_4 = pct_pf_gt_1 >= 70.0
        crit_5 = pct_pf_gt_13 >= 50.0
        
        passed = crit_1 and crit_2 and crit_3 and crit_4 and crit_5
        
        print(f"1. Avg PF > 1.3: {round(avg_pf, 3)} -> {'PASS' if crit_1 else 'FAIL'}")
        print(f"2. Median PF > 1.2: {round(median_pf, 3)} -> {'PASS' if crit_2 else 'FAIL'}")
        print(f"3. Max Monthly DD < 15R: {max_dd}R -> {'PASS' if crit_3 else 'FAIL'}")
        print(f"4. >70% Folds PF > 1.0: {round(pct_pf_gt_1, 1)}% -> {'PASS' if crit_4 else 'FAIL'}")
        print(f"5. >50% Folds PF > 1.3: {round(pct_pf_gt_13, 1)}% -> {'PASS' if crit_5 else 'FAIL'}")
        
        avg_trades = t_df['trades'].mean()
        print(f"Average Trades per Month: {round(avg_trades, 1)}")
        print(f"Overall Status: {'APPROVED' if passed else 'REJECTED'}")

if __name__ == "__main__":
    run_walk_forward()
