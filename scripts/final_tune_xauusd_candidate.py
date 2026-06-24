import os
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta
from xgboost import XGBClassifier

def train_xgb(X_train, y_train, spw=1.0):
    model = XGBClassifier(
        n_estimators=300,
        learning_rate=0.01,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
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

def run_optimization():
    print("--- Starting Final Tuning for XAUUSDm ---")
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
    
    features = [
        "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "atr_pct", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance",
        "recent_high_20_distance_pct", "recent_low_20_distance_pct"
    ]
    
    tm = 12
    spw_list = [1.00, 1.05, 1.10, 1.15]
    thresholds = [0.500, 0.505, 0.510, 0.515]
    test_months = 3
    
    results = []
    
    for spw in spw_list:
        print(f"\nEvaluating SPW={spw:.2f}")
        current_start = start_date.replace(day=1) + relativedelta(months=1)
        
        config_metrics = {th: {
            "total_trades": 0, "total_net_profit": 0, "total_gross_profit": 0, "total_gross_loss": 0,
            "passed_windows": 0, "num_windows": 0, "max_dd_overall": 0, "max_consec_loss": 0
        } for th in thresholds}
        
        while True:
            train_end = current_start + relativedelta(months=tm)
            test_end = train_end + relativedelta(months=test_months)
            
            if test_end > end_date:
                break
                
            train_df = df[(df['timestamp'] >= current_start) & (df['timestamp'] < train_end)]
            test_df = df[(df['timestamp'] >= train_end) & (df['timestamp'] < test_end)]
            
            if len(train_df) < 500 or len(test_df) < 50:
                current_start += relativedelta(months=test_months)
                continue
                
            X_train = train_df[features]
            y_train = train_df['label'].values
            X_test = test_df[features]
            y_test = test_df['label'].values
            
            model = train_xgb(X_train, y_train, spw)
            probs = model.predict_proba(X_test)[:, 1]
            
            for th in thresholds:
                m = calc_metrics(probs, y_test, th)
                c = config_metrics[th]
                
                c["num_windows"] += 1
                c["total_trades"] += m["trades"]
                c["total_net_profit"] += m["net_profit"]
                
                if m["pf"] > 0:
                    wins = (probs >= th) & (y_test == 1)
                    losses = (probs >= th) & (y_test == 0)
                    c["total_gross_profit"] += wins.sum() * 2.5
                    c["total_gross_loss"] += losses.sum() * 1.0
                    
                if m["max_dd"] > c["max_dd_overall"]:
                    c["max_dd_overall"] = m["max_dd"]
                    
                if m["consec_loss"] > c["max_consec_loss"]:
                    c["max_consec_loss"] = m["consec_loss"]
                    
                if m["pf"] > 1.3 and m["max_dd"] < 15 and m["trades"] >= 2:
                    c["passed_windows"] += 1
                    
            current_start += relativedelta(months=test_months)
            
        for th in thresholds:
            c = config_metrics[th]
            n_win = c["num_windows"]
            if n_win > 0:
                total_months = n_win * test_months
                tpm = c["total_trades"] / total_months if total_months > 0 else 0
                
                overall_pf = c["total_gross_profit"] / c["total_gross_loss"] if c["total_gross_loss"] > 0 else c["total_gross_profit"]
                overall_win_rate = (c["total_gross_profit"]/2.5) / c["total_trades"] * 100 if c["total_trades"] > 0 else 0
                
                results.append({
                    "SPW": spw,
                    "Thresh": th,
                    "Trades": c["total_trades"],
                    "TPM": tpm,
                    "WinRate": overall_win_rate,
                    "PF": overall_pf,
                    "NetProf": c["total_net_profit"],
                    "MaxDD": c["max_dd_overall"],
                    "MaxLossStreak": c["max_consec_loss"],
                    "PassedWin": f"{c['passed_windows']}/{n_win}"
                })
                
    print("\n=================================================================================================================")
    print("                                WALK FORWARD FINAL TUNING RESULTS                                                ")
    print("=================================================================================================================")
    print(f"{'SPW':<4} | {'Thrsh':<5} | {'Trd':<4} | {'TPM':<5} | {'Win%':<6} | {'PF':<5} | {'NetProf':<7} | {'MaxDD%':<6} | {'ConsLoss':<8} | {'PassWin'}")
    print("-" * 115)
    
    # Sort logically
    results.sort(key=lambda x: (x["SPW"], x["Thresh"]))
    
    for r in results:
        tpm_str = f"{r['TPM']:.2f}"
        win_str = f"{r['WinRate']:.1f}%"
        pf_str = f"{r['PF']:.2f}"
        np_str = f"{r['NetProf']:+.1f}R"
        dd_str = f"{r['MaxDD']:.1f}%"
        
        print(f"{r['SPW']:<4.2f} | {r['Thresh']:<5.3f} | {r['Trades']:<4} | {tpm_str:<5} | {win_str:>5} | {pf_str:>4} | {np_str:>7} | {dd_str:>5} | {r['MaxLossStreak']:<8} | {r['PassedWin']}")
        
    print("=================================================================================================================")

if __name__ == "__main__":
    run_optimization()
