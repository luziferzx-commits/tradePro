import pandas as pd
import numpy as np
import xgboost as xgb
import os
import random
import itertools
from datetime import datetime
from gqos.research.ml.validation import CombinatorialPurgedCV
from gqos.research.statistics.pbo import ProbabilityOfBacktestOverfitting

def block_bootstrap_trades(trades_df, n_iterations=1000, block_size=5):
    """
    Monte Carlo Block Bootstrap
    Preserves streak dependency by sampling blocks of consecutive trades.
    """
    if len(trades_df) < block_size:
        return []
        
    returns = trades_df['result_r'].values
    n_trades = len(returns)
    
    # Create blocks
    blocks = [returns[i:i+block_size] for i in range(n_trades - block_size + 1)]
    
    bootstrapped_pfs = []
    
    for _ in range(n_iterations):
        # Sample blocks with replacement until we reach original sequence length
        sampled_sequence = []
        while len(sampled_sequence) < n_trades:
            block = random.choice(blocks)
            sampled_sequence.extend(block)
            
        sampled_sequence = np.array(sampled_sequence[:n_trades])
        
        wins = sampled_sequence[sampled_sequence > 0].sum()
        losses = abs(sampled_sequence[sampled_sequence <= 0].sum())
        
        pf = wins / losses if losses > 0 else 99.9
        bootstrapped_pfs.append(pf)
        
    return bootstrapped_pfs

def evaluate_predictions(y_pred, df_test):
    trades_mask = y_pred == 1
    trades_df = df_test[trades_mask].copy()
    
    if trades_df.empty:
        return {"trades": 0, "pf": 0.0, "net_r": 0.0, "returns": [], "trades_df": trades_df}
        
    wins = trades_df[trades_df['result_r'] > 0]['result_r'].sum()
    losses = abs(trades_df[trades_df['result_r'] <= 0]['result_r'].sum())
    
    pf = wins / losses if losses > 0 else (99.9 if wins > 0 else 0.0)
    
    return {
        "trades": len(trades_df),
        "pf": pf,
        "net_r": trades_df['result_r'].sum(),
        "returns": trades_df['result_r'].values.tolist(),
        "trades_df": trades_df
    }

def generate_random_grid(n=20, seed=42):
    random.seed(seed)
    params = {
        'max_depth': [2, 3, 4],
        'learning_rate': [0.01, 0.03, 0.05],
        'n_estimators': [100, 300],
        'subsample': [0.7, 0.9]
    }
    keys, values = zip(*params.items())
    all_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    return random.sample(all_combinations, min(n, len(all_combinations)))

def run_v33():
    print("--- Phase 3: Walk-Forward V33 (CPCV + Block Bootstrap) ---")
    
    # Try to load dataset. If multiple exist, pick the newest.
    import glob
    files = glob.glob("datasets/*/*.csv")
    if not files:
        # Fallback to standard if specific not found
        files = glob.glob("datasets/*.csv")
    
    if not files:
        print("No datasets found!")
        return
        
    data_file = files[-1] # pick latest
    for f in files:
        if "XAUUSDm" in f:
            data_file = f
            break
            
    print(f"Loading dataset: {data_file}")
    df = pd.read_csv(data_file)
    
    features = [
        "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
    ]
    
    # Check if features exist, use intersection
    available_features = [f for f in features if f in df.columns]
    
    # 1. Dynamic Embargo and Purge
    # XAUUSDm M5: Typical holding time is up to 24 hours = 288 candles.
    # We enforce a strict max trade duration floor.
    max_trade_duration_candles = 200
    embargo_candles = max(max_trade_duration_candles, 50)
    purge_candles = 10 # Just to clear immediate boundary
    
    n_samples = len(df)
    purge_pct = purge_candles / n_samples
    embargo_pct = embargo_candles / n_samples
    
    print(f"Total Samples: {n_samples}")
    print(f"Dynamic Embargo: {embargo_candles} candles ({embargo_pct:.4f}%)")
    
    # Setup CPCV (6 groups, test on 2 -> 15 combinations/paths)
    cpcv = CombinatorialPurgedCV(n_groups=6, k_test_groups=2, purge_pct=purge_pct, embargo_pct=embargo_pct)
    
    combinations = generate_random_grid(20) # 20 strategies
    
    # Matrices for PBO calculation: shape (num_paths, num_strategies)
    # CPCV with 6 choose 2 gives 15 paths
    is_metrics = np.zeros((15, len(combinations)))
    oos_metrics = np.zeros((15, len(combinations)))
    total_trades_strategies = np.zeros(len(combinations))
    
    all_oos_trades = {i: [] for i in range(len(combinations))}
    
    print("Running CPCV Evaluation Engine...")
    
    splits = list(cpcv.split(df))
    
    for c_idx, config in enumerate(combinations):
        total_oos_trades = 0
        
        for path_idx, (train_idx, test_idx) in enumerate(splits):
            X_train = df.iloc[train_idx][available_features]
            y_train = df.iloc[train_idx]['label']
            X_test = df.iloc[test_idx][available_features]
            df_test = df.iloc[test_idx]
            
            if len(y_train) < 50 or len(X_test) == 0:
                continue
                
            model = xgb.XGBClassifier(**config, random_state=42, eval_metric='logloss', n_jobs=-1)
            model.fit(X_train, y_train)
            
            # In-Sample Performance (for PBO ranking)
            y_pred_is = model.predict(X_train)
            is_eval = evaluate_predictions(y_pred_is, df.iloc[train_idx])
            is_metrics[path_idx, c_idx] = is_eval['pf']
            
            # Out-of-Sample Performance
            y_pred_oos = model.predict(X_test)
            oos_eval = evaluate_predictions(y_pred_oos, df_test)
            oos_metrics[path_idx, c_idx] = oos_eval['pf']
            
            total_oos_trades += oos_eval['trades']
            if not oos_eval['trades_df'].empty:
                all_oos_trades[c_idx].append(oos_eval['trades_df'])
                
        total_trades_strategies[c_idx] = total_oos_trades
        print(f"Config {c_idx+1}/{len(combinations)} | OOS Trades: {total_oos_trades} | Avg OOS PF: {np.mean(oos_metrics[:, c_idx]):.2f}")
    
    # 2. PBO Calculation
    print("\nCalculating PBO (Probability of Backtest Overfitting)...")
    pbo_score = ProbabilityOfBacktestOverfitting.calculate_cscv(is_metrics, oos_metrics)
    pbo_pct = pbo_score * 100
    print(f"PBO Score: {pbo_pct:.2f}%")
    
    # Senior Hardening: PBO Sample Threshold Check
    avg_trades_across_configs = np.mean(total_trades_strategies)
    if avg_trades_across_configs < 300:
        print(f"WARNING: PBO is mathematically INVALID because sample size is too small (Avg Trades: {avg_trades_across_configs:.1f} < 300).")
    elif pbo_pct > 15.0:
        print(f"REJECTED: PBO {pbo_pct:.1f}% exceeds institutional threshold (<= 15%). Strategy is overfitted.")
    else:
        print(f"APPROVED: PBO {pbo_pct:.1f}% is within acceptable institutional bounds.")
        
    # 3. Monte Carlo Block Bootstrapping for the most "stable" model
    # Model selection prioritizes STABILITY > PROFIT.
    # Stability = low variance of OOS PF across all 15 paths
    variances = np.var(oos_metrics, axis=0)
    most_stable_idx = np.argmin(variances)
    
    print(f"\nSelecting Most Stable Config (Index {most_stable_idx}):")
    print(combinations[most_stable_idx])
    
    p05_str = "N/A"
    p50_str = "N/A"
    
    best_oos_df_list = all_oos_trades[most_stable_idx]
    if best_oos_df_list:
        combined_trades = pd.concat(best_oos_df_list)
        
        print(f"\nRunning Block Bootstrap Monte Carlo on selected model (Trades: {len(combined_trades)})...")
        boot_pfs = block_bootstrap_trades(combined_trades, n_iterations=1000, block_size=10)
        
        if boot_pfs:
            p05 = np.percentile(boot_pfs, 5)
            p50 = np.percentile(boot_pfs, 50)
            p95 = np.percentile(boot_pfs, 95)
            
            p05_str = f"{p05:.2f}"
            p50_str = f"{p50:.2f}"
            
            print(f"Monte Carlo Profit Factor Distribution:")
            print(f"  5th Percentile (Worst-Case): {p05_str}")
            print(f" 50th Percentile (Median)    : {p50_str}")
            print(f" 95th Percentile (Best-Case) : {p95:.2f}")
            
            if p05 < 1.0:
                print("REJECTED: 5th Percentile PF is < 1.0. System cannot survive bad luck streaks.")
            else:
                print("APPROVED: System is statistically robust against bad streaks.")
        else:
            p05_str = "N/A"
            p50_str = "N/A"
                
    # 4. Save Artifact Report
    report = f"""# Phase 3 Integrity Report

## CPCV Validation Parameters
- **Embargo Size**: {embargo_candles} candles
- **Purge Size**: {purge_candles} candles
- **Number of Paths**: 15 (6 choose 2)
- **Strategy Grid Size**: {len(combinations)} configs

## Overfitting Analytics (PBO)
- **PBO Score**: {pbo_pct:.2f}%
- **Average OOS Trades**: {avg_trades_across_configs:.1f}
- **Status**: {"INVALID (Trades < 300)" if avg_trades_across_configs < 300 else ("REJECTED" if pbo_pct > 15 else "APPROVED")}

## Most Stable Strategy Analysis
The model selection mechanism prioritized the lowest variance across all 15 OOS paths.
- **Config**: `{combinations[most_stable_idx]}`
- **Mean OOS PF**: {np.mean(oos_metrics[:, most_stable_idx]):.2f}
- **OOS PF Variance**: {variances[most_stable_idx]:.4f}

### Monte Carlo Block Bootstrapping
- **5th Percentile PF (Worst)**: {p05_str}
- **50th Percentile PF (Median)**: {p50_str}
"""
    os.makedirs("docs", exist_ok=True)
    with open("docs/phase3_integrity_report.md", "w", encoding='utf-8') as f:
        f.write(report)
        
    print("\nReport saved to docs/phase3_integrity_report.md")

if __name__ == "__main__":
    run_v33()
