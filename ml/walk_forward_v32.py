import pandas as pd
import numpy as np
import xgboost as xgb
import os
import random
import itertools
from datetime import datetime

def simulate_kill_switch(trades_df, limit_r):
    if trades_df.empty:
        return trades_df
        
    trades_df = trades_df.copy().reset_index(drop=True)
    trades_df['cum_r'] = trades_df['result_r'].cumsum()
    
    breach = trades_df[trades_df['cum_r'] <= -limit_r]
    if not breach.empty:
        first_breach_idx = breach.index[0]
        return trades_df.iloc[:first_breach_idx + 1]
    return trades_df

def evaluate_predictions(y_pred, df_test, ks_limit):
    trades_mask = y_pred == 1
    trades_df = df_test[trades_mask].copy()
    
    if ks_limit > 0:
        trades_df = simulate_kill_switch(trades_df, ks_limit)
        
    if trades_df.empty:
        return {"trades": 0, "pf": 0.0, "max_dd_r": 0.0, "net_r": 0.0, "regime_pfs": {}}
        
    wins = trades_df[trades_df['result_r'] > 0]['result_r'].sum()
    losses = abs(trades_df[trades_df['result_r'] <= 0]['result_r'].sum())
    
    pf = wins / losses if losses > 0 else float('inf')
    if pf == float('inf') and wins > 0:
        pf = 99.9
    elif pf == float('inf'):
        pf = 0.0
        
    trades_df['cum_r'] = trades_df['result_r'].cumsum()
    trades_df['peak'] = trades_df['cum_r'].cummax()
    trades_df['dd'] = trades_df['peak'] - trades_df['cum_r']
    max_dd = trades_df['dd'].max()
    
    regime_pfs = {}
    for r_state in ['TRENDING_UP', 'TRENDING_DOWN', 'RANGING', 'HIGH_VOLATILITY', 'NORMAL_VOLATILITY']:
        mask = (trades_df['trend_state'] == r_state) | (trades_df['volatility_state'] == r_state)
        r_trades = trades_df[mask]
        r_wins = r_trades[r_trades['result_r'] > 0]['result_r'].sum()
        r_loss = abs(r_trades[r_trades['result_r'] <= 0]['result_r'].sum())
        r_pf = r_wins / r_loss if r_loss > 0 else (99.9 if r_wins > 0 else 0)
        regime_pfs[r_state] = round(r_pf, 3)
        
    return {
        "trades": len(trades_df),
        "pf": round(pf, 3),
        "max_dd_r": round(max_dd, 2),
        "net_r": round(trades_df['cum_r'].iloc[-1] if not trades_df.empty else 0, 2),
        "regime_pfs": regime_pfs
    }

def generate_random_grid(n=100, seed=42):
    random.seed(seed)
    params = {
        'max_depth': [2, 3, 4],
        'learning_rate': [0.01, 0.03, 0.05],
        'n_estimators': [100, 300, 500],
        'subsample': [0.7, 0.9],
        'colsample_bytree': [0.7, 0.9],
        'reg_alpha': [0, 0.1, 1],
        'reg_lambda': [1, 3, 10]
    }
    keys, values = zip(*params.items())
    all_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    return random.sample(all_combinations, n)

def run_v32():
    df = pd.read_csv("datasets/ml_volatility_expansion.csv")
    df['datetime'] = pd.to_datetime(df['timestamp'])
    df['month'] = df['datetime'].dt.to_period('M')
    
    months = sorted(df['month'].unique())
    print(f"Total months: {len(months)}")
    
    features = [
        "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
    ]
    
    windows = [6, 9, 12]
    kill_switches = [0, 5, 8, 10]
    prob_threshold = 0.55
    
    combinations = generate_random_grid(100)
    config_results = []
    
    for c_idx, config in enumerate(combinations):
        for w in windows:
            print(f"Config {c_idx+1}/100 | Window {w} months")
            folds_data = {ks: [] for ks in kill_switches}
            
            for i in range(len(months) - w):
                train_months = months[i:i+w]
                test_month = months[i+w]
                
                train_mask = df['month'].isin(train_months)
                test_mask = df['month'] == test_month
                
                X_train = df[train_mask][features]
                y_train = df[train_mask]['label']
                df_test = df[test_mask]
                X_test = df_test[features]
                
                if len(y_train) < 50 or len(X_test) == 0:
                    continue
                    
                pos_count = sum(y_train)
                neg_count = len(y_train) - pos_count
                scale_weight = neg_count / pos_count if pos_count > 0 else 1.0
                
                model = xgb.XGBClassifier(
                    **config,
                    scale_pos_weight=scale_weight,
                    random_state=42,
                    eval_metric='logloss',
                    n_jobs=-1
                )
                model.fit(X_train, y_train)
                
                y_pred_proba = model.predict_proba(X_test)[:, 1]
                y_pred = (y_pred_proba >= prob_threshold).astype(int)
                
                for ks in kill_switches:
                    metrics = evaluate_predictions(y_pred, df_test, ks)
                    folds_data[ks].append(metrics)
                    
            for ks in kill_switches:
                f_metrics = folds_data[ks]
                if not f_metrics:
                    continue
                    
                pfs = [m['pf'] for m in f_metrics]
                dds = [m['max_dd_r'] for m in f_metrics]
                
                avg_pf = np.mean(pfs)
                med_pf = np.median(pfs)
                max_dd = np.max(dds)
                
                pct_gt_1 = (sum(1 for pf in pfs if pf > 1.0) / len(pfs)) * 100
                pct_gt_13 = (sum(1 for pf in pfs if pf > 1.3) / len(pfs)) * 100
                
                config_results.append({
                    "config_idx": c_idx,
                    "window": w,
                    "kill_switch": ks,
                    "avg_pf": round(avg_pf, 3),
                    "med_pf": round(med_pf, 3),
                    "max_dd_r": round(max_dd, 2),
                    "pct_gt_1": round(pct_gt_1, 1),
                    "pct_gt_13": round(pct_gt_13, 1),
                    "avg_trades": round(np.mean([m['trades'] for m in f_metrics]), 1),
                    "config": str(config)
                })
                
    res_df = pd.DataFrame(config_results)
    top10 = res_df.sort_values(by=['avg_pf'], ascending=False).head(10)
    
    os.makedirs("ml/reports", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_file = f"ml/reports/v32_top10_configs_{today}.csv"
    top10.to_csv(out_file, index=False)
    print(f"\nTop 10 configurations saved to {out_file}")
    
    print("\n--- TOP 5 CONFIGURATIONS ---")
    for _, row in top10.head(5).iterrows():
        print(f"Window: {row['window']}m | KS: {row['kill_switch']}R | Avg PF: {row['avg_pf']} | Max DD: {row['max_dd_r']}R | >1.3: {row['pct_gt_13']}%")
        print(f"Config: {row['config']}\n")

if __name__ == "__main__":
    run_v32()
