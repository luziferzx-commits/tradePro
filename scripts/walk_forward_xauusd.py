import os
import json
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta
from xgboost import XGBClassifier

def train_xgb(X_train, y_train):
    model = XGBClassifier(
        n_estimators=300,
        learning_rate=0.01,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='logloss'
    )
    model.fit(X_train, y_train)
    return model

def calc_metrics(probs, y, threshold=0.55):
    trades = probs >= threshold
    num_trades = trades.sum()
    if num_trades == 0:
        return {"trades": 0, "win_rate": 0, "pf": 0, "avg_prob": 0, "max_dd": 0, "net_profit": 0, "avg_return": 0, "consec_loss": 0}
        
    wins = (trades & (y == 1)).sum()
    losses = (trades & (y == 0)).sum()
    win_rate = wins / num_trades if num_trades > 0 else 0
    
    gross_profit = wins * 2.5
    gross_loss = losses * 1.0
    pf = gross_profit / gross_loss if gross_loss > 0 else gross_profit
    net_profit = gross_profit - gross_loss
    
    avg_prob = probs[trades].mean() if num_trades > 0 else 0
    avg_return = net_profit / num_trades
    
    # Calculate Max DD and Consec Loss
    balance = 100.0
    peak = 100.0
    max_dd = 0.0
    current_loss_streak = 0
    max_loss_streak = 0
    
    for i in range(len(trades)):
        if trades[i]:
            if y[i] == 1:
                balance += 2.5
                current_loss_streak = 0
            else:
                balance -= 1.0
                current_loss_streak += 1
                if current_loss_streak > max_loss_streak:
                    max_loss_streak = current_loss_streak
                    
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak * 100
            if dd > max_dd:
                max_dd = dd
                
    return {
        "trades": num_trades,
        "win_rate": win_rate * 100,
        "pf": pf,
        "avg_prob": avg_prob,
        "max_dd": max_dd,
        "net_profit": net_profit,
        "avg_return": avg_return,
        "consec_loss": max_loss_streak
    }

def run_walk_forward():
    print("--- Starting XAUUSDm Walk Forward Validation ---")
    dataset_path = "datasets/XAUUSDm/XAUUSDm_dataset_atr_2_0_v001.csv"
    
    if not os.path.exists(dataset_path):
        print(f"Dataset not found at {dataset_path}")
        return
        
    df = pd.read_csv(dataset_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    start_date = df['timestamp'].min()
    end_date = df['timestamp'].max()
    print(f"Data ranges from {start_date} to {end_date}")
    
    # Define features based on recent Quant Bug fix
    features = [
        "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "atr_pct", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance",
        "recent_high_20_distance_pct", "recent_low_20_distance_pct"
    ]
    
    # 12 months train, 3 months test, slide by 3 months
    train_months = 12
    test_months = 3
    
    # Align to start of next month for clean windows
    current_start = start_date.replace(day=1) + relativedelta(months=1)
    
    windows = []
    window_idx = 1
    
    while True:
        train_end = current_start + relativedelta(months=train_months)
        test_end = train_end + relativedelta(months=test_months)
        
        if test_end > end_date:
            break
            
        train_df = df[(df['timestamp'] >= current_start) & (df['timestamp'] < train_end)]
        test_df = df[(df['timestamp'] >= train_end) & (df['timestamp'] < test_end)]
        
        if len(train_df) < 500 or len(test_df) < 50:
            current_start += relativedelta(months=test_months)
            continue
            
        X_train = train_df[features]
        y_train = train_df['label']
        
        X_test = test_df[features]
        y_test = test_df['label']
        
        print(f"\nTraining Window {window_idx}...")
        print(f"Train: {current_start.strftime('%Y-%m')} to {train_end.strftime('%Y-%m')} ({len(train_df)} samples)")
        print(f"Test : {train_end.strftime('%Y-%m')} to {test_end.strftime('%Y-%m')} ({len(test_df)} samples)")
        
        model = train_xgb(X_train, y_train)
        probs = model.predict_proba(X_test)[:, 1]
        
        metrics = calc_metrics(probs, y_test.values)
        metrics['train_period'] = f"{current_start.strftime('%Y-%m')} to {train_end.strftime('%Y-%m')}"
        metrics['test_period'] = f"{train_end.strftime('%Y-%m')} to {test_end.strftime('%Y-%m')}"
        metrics['window'] = window_idx
        
        windows.append(metrics)
        
        current_start += relativedelta(months=test_months)
        window_idx += 1
        
    print("\n=========================================================================================================")
    print("                                   WALK FORWARD OUT-OF-SAMPLE RESULTS                                    ")
    print("=========================================================================================================")
    print(f"{'Win':<4} | {'Test Period':<18} | {'Trd':<4} | {'Win%':<6} | {'PF':<5} | {'MaxDD%':<6} | {'NetProf':<7} | {'AvgProb':<7} | {'ConsLoss':<8}")
    print("-" * 105)
    
    passed_windows = 0
    total_trades = 0
    total_net_profit = 0
    
    for w in windows:
        trd = w['trades']
        win_p = w['win_rate']
        pf = w['pf']
        dd = w['max_dd']
        np_val = w['net_profit']
        ap = w['avg_prob']
        cl = w['consec_loss']
        tp = w['test_period']
        wid = w['window']
        
        print(f"{wid:<4} | {tp:<18} | {trd:<4} | {win_p:>5.1f}% | {pf:>4.2f} | {dd:>5.2f}% | {np_val:>+6.1f}R | {ap:>6.3f}  | {cl:<8}")
        
        total_trades += trd
        total_net_profit += np_val
        if pf > 1.3 and dd < 15 and trd > 5:
            passed_windows += 1
            
    print("=========================================================================================================")
    
    if len(windows) > 0:
        pass_rate = (passed_windows / len(windows)) * 100
        print(f"\nTotal Out-of-Sample Trades: {total_trades}")
        print(f"Total Out-of-Sample Net Profit: {total_net_profit:+.1f} R")
        print(f"Windows Passing Criteria (PF>1.3, DD<15%, Trd>5): {passed_windows}/{len(windows)} ({pass_rate:.1f}%)")
        
        if pass_rate >= 70 and total_net_profit > 0:
            print("\n>>> WALK FORWARD VALIDATION PASSED <<<")
            print("The model shows robust generalizability and is NOT severely overfit.")
        else:
            print("\n>>> WALK FORWARD VALIDATION FAILED <<<")
            print("The model's performance is inconsistent across time periods.")

if __name__ == "__main__":
    run_walk_forward()
