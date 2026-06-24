"""scripts/walk_forward_validation.py — Walk-forward validation for XGBoost."""
import os
import sys
import glob
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

# Add root directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logger = logging.getLogger("WalkForward")
logging.basicConfig(level=logging.INFO, format="%(message)s")

FEATURES = [
    "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
    "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc", "is_high_volatility", "is_buy",
    "recent_high_20_distance", "recent_low_20_distance"
]

TARGET = "label"

def simulate_pnl(y_true, y_pred):
    """Simulate P&L for taken trades. Win = +2R, Loss = -1R."""
    trades = (y_pred == 1)
    
    if trades.sum() == 0:
        return 0, 0.0, 0.0, 0.0, 0.0
        
    wins = (y_true == 1) & trades
    losses = (y_true == 0) & trades
    
    n_trades = trades.sum()
    n_wins = wins.sum()
    n_losses = losses.sum()
    
    win_rate = n_wins / n_trades
    total_r = (n_wins * 2.0) + (n_losses * -1.0)
    expectancy_r = total_r / n_trades
    
    # Max Drawdown
    pnl_seq = np.where(y_true[trades] == 1, 2.0, -1.0)
    cum_r = np.cumsum(pnl_seq)
    peak_r = np.maximum.accumulate(cum_r)
    dd_r = peak_r - cum_r
    max_dd_r = dd_r.max() if len(dd_r) > 0 else 0.0
    
    return n_trades, win_rate, expectancy_r, total_r, max_dd_r

def run_walk_forward():
    print("=" * 70)
    print(" WALK-FORWARD VALIDATION ")
    print("=" * 70)

    dataset_files = glob.glob("datasets/training_data_*.csv")
    if not dataset_files:
        logger.error("No dataset found in datasets/ directory.")
        return
        
    latest_file = max(dataset_files)
    logger.info(f"Using dataset: {latest_file}")
    
    df = pd.read_csv(latest_file)
    
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values("timestamp").reset_index(drop=True)
        
    missing = [f for f in FEATURES if f not in df.columns]
    if missing:
        logger.error(f"Missing features: {missing}")
        return

    n_splits = 5
    fold_size = len(df) // (n_splits + 1)
    
    if fold_size < 100:
        logger.error("Dataset too small for 5 walk-forward splits.")
        return

    fold_metrics = []
    report_lines = []
    
    report_lines.append(f"Walk-Forward Validation Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append(f"Dataset: {latest_file} (Total rows: {len(df)})")
    report_lines.append("-" * 70)

    for k in range(1, n_splits + 1):
        # train = data[0 : k * fold_size]
        # test  = data[k * fold_size : (k+1) * fold_size]
        train_end = k * fold_size
        test_end = (k + 1) * fold_size
        
        train_df = df.iloc[0:train_end]
        test_df = df.iloc[train_end:test_end]
        
        X_train, y_train = train_df[FEATURES], train_df[TARGET]
        X_test, y_test = test_df[FEATURES], test_df[TARGET]
        
        n_pos = sum(y_train == 1)
        n_neg = sum(y_train == 0)
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0
        
        model = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            scale_pos_weight=scale_pos_weight, eval_metric='logloss',
            random_state=42
        )
        
        model.fit(X_train, y_train, verbose=False)
        
        # We use a fixed threshold of 0.50 for walk-forward baseline, 
        # or could dynamically tune it per fold. We'll use 0.50 here.
        threshold = 0.50
        y_probs = model.predict_proba(X_test)[:, 1]
        y_pred = (y_probs >= threshold).astype(int)
        
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        
        try:
            auc = roc_auc_score(y_test, y_probs)
        except ValueError:
            auc = 0.5
            
        n_trades, win_rate, exp_r, total_r, max_dd_r = simulate_pnl(y_test.values, y_pred)
        
        metrics = {
            "Fold": k,
            "Train_Size": len(X_train), "Test_Size": len(X_test),
            "Acc": acc, "Prec": prec, "Rec": rec, "F1": f1, "AUC": auc,
            "Trades": n_trades, "WinRate": win_rate, "Exp_R": exp_r, 
            "Total_R": total_r, "MaxDD_R": max_dd_r
        }
        fold_metrics.append(metrics)
        
        line = (f"Fold {k}: Acc={acc:.2f}, F1={f1:.2f}, AUC={auc:.2f} | "
                f"Trades={n_trades}, WR={win_rate:.0%}, Exp={exp_r:.2f}R, Total={total_r:.2f}R, DD={max_dd_r:.2f}R")
        print(line)
        report_lines.append(line)

    print("-" * 70)
    report_lines.append("-" * 70)
    
    # Aggregation
    f1_scores = [m["F1"] for m in fold_metrics]
    exp_r_scores = [m["Exp_R"] for m in fold_metrics]
    
    mean_f1 = np.mean(f1_scores)
    std_f1 = np.std(f1_scores)
    mean_exp_r = np.mean(exp_r_scores)
    total_trades = sum(m["Trades"] for m in fold_metrics)
    total_net_r = sum(m["Total_R"] for m in fold_metrics)
    
    agg_line1 = f"AGGREGATE: Avg F1 = {mean_f1:.2f} ± {std_f1:.2f}, Total Trades = {total_trades}, Net R = {total_net_r:.2f}R"
    agg_line2 = f"AGGREGATE: Avg Expectancy = {mean_exp_r:.2f}R per trade"
    
    print(agg_line1)
    print(agg_line2)
    report_lines.append(agg_line1)
    report_lines.append(agg_line2)
    
    print("-" * 70)
    report_lines.append("-" * 70)

    # Stability Checks
    checks_passed = True
    if std_f1 > 0.15:
        msg = "⚠ WARNING: Model unstable across time periods (high F1 variance)"
        print(msg)
        report_lines.append(msg)
        checks_passed = False
        
    for i, f1 in enumerate(f1_scores, 1):
        if f1 < 0.40:
            msg = f"⚠ WARNING: Fold {i} underperforms (F1 = {f1:.2f} < 0.40)"
            print(msg)
            report_lines.append(msg)
            checks_passed = False
            
    if mean_exp_r < 0.10:
        msg = f"❌ FAIL: Edge too weak for live deployment (Avg Exp = {mean_exp_r:.2f}R < 0.10R)"
        print(msg)
        report_lines.append(msg)
        checks_passed = False

    if checks_passed:
        msg = "✅ PASS: Model shows consistent edge across time"
        print(msg)
        report_lines.append(msg)

    print("=" * 70)
    
    # Save Report
    os.makedirs("reports", exist_ok=True)
    today_str = datetime.now().strftime("%Y%m%d")
    report_path = f"reports/walk_forward_report_{today_str}.txt"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")
        
    logger.info(f"Report saved to {report_path}")

if __name__ == "__main__":
    run_walk_forward()
