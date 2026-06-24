import pandas as pd
import numpy as np
import xgboost as xgb
import os
import random
from ml.dataset_builder import build_dataset
from analytics.auditor import auditor

def get_walk_forward_trades(dataset_path, prob_threshold, config, return_feature_importances=False):
    df = pd.read_csv(dataset_path)
    df['datetime'] = pd.to_datetime(df['timestamp'])
    df['month'] = df['datetime'].dt.to_period('M')
    
    months = sorted(df['month'].unique())
    features = [
        "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
        "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
        "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
    ]
    
    w = 12 # using the best window from V3.2
    all_trades = []
    feature_importances_list = []
    
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
        
        if return_feature_importances:
            feature_importances_list.append(model.feature_importances_)
            
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        
        trades_mask = y_pred_proba >= prob_threshold
        trades_df = df_test[trades_mask].copy()
        
        trades_df['pred_prob'] = y_pred_proba[trades_mask]
        
        if not trades_df.empty:
            all_trades.append(trades_df)
            
    final_trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    
    if not final_trades_df.empty:
        from analytics.auditor import auditor
        auditor.export_csv(f"walk_forward_thr_{prob_threshold}.csv", final_trades_df)
    
    if return_feature_importances:
        return final_trades_df, feature_importances_list, features
    return final_trades_df

def calc_pf(series):
    wins = series[series > 0].sum()
    losses = abs(series[series <= 0].sum())
    if losses == 0:
        return 99.9 if wins > 0 else 0.0
    return wins / losses

def calc_max_dd(arr):
    cum = np.cumsum(arr)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    return np.max(dd) if len(dd) > 0 else 0.0

def monte_carlo_simulation(trades_df, iterations=10000):
    print(f"\nRunning {iterations} Monte Carlo Simulations...")
    results = []
    base_r = trades_df['result_r'].values
    n_trades = len(base_r)
    
    for _ in range(iterations):
        sim_r = np.random.permutation(base_r)
        
        miss_mask = np.random.rand(n_trades) > 0.05
        sim_r = sim_r[miss_mask]
        
        slippage = np.random.normal(0.1, 0.05, len(sim_r))
        slippage = np.clip(slippage, 0, 0.5) 
        
        sim_r = sim_r - slippage
        
        pf = calc_pf(sim_r)
        max_dd = calc_max_dd(sim_r)
        exp = np.mean(sim_r)
        
        results.append({"pf": pf, "max_dd": max_dd, "exp": exp})
        
    res_df = pd.DataFrame(results)
    auditor.export_csv("montecarlo.csv", res_df)
    
    print("Monte Carlo Results:")
    print(f"Median PF: {res_df['pf'].median():.3f}")
    print(f"95th Percentile Max DD: {res_df['max_dd'].quantile(0.95):.2f}R")
    print(f"Median Expectancy: {res_df['exp'].median():.3f}R")
    return res_df

def bootstrap_analysis(trades_df, iterations=5000):
    print(f"\nRunning {iterations} Bootstrap Samples...")
    results = []
    base_r = trades_df['result_r'].values
    n_trades = len(base_r)
    
    for _ in range(iterations):
        sim_r = np.random.choice(base_r, size=n_trades, replace=True)
        pf = calc_pf(sim_r)
        max_dd = calc_max_dd(sim_r)
        exp = np.mean(sim_r)
        results.append({"pf": pf, "max_dd": max_dd, "exp": exp})
        
    res_df = pd.DataFrame(results)
    auditor.export_csv("bootstrap.csv", res_df)
    
    ci_pf = (res_df['pf'].quantile(0.025), res_df['pf'].quantile(0.975))
    ci_exp = (res_df['exp'].quantile(0.025), res_df['exp'].quantile(0.975))
    ci_dd = (res_df['max_dd'].quantile(0.025), res_df['max_dd'].quantile(0.975))
    
    print("Bootstrap 95% Confidence Intervals:")
    print(f"Profit Factor: {ci_pf[0]:.3f} to {ci_pf[1]:.3f}")
    print(f"Expectancy: {ci_exp[0]:.3f}R to {ci_exp[1]:.3f}R")
    print(f"Max DD: {ci_dd[0]:.2f}R to {ci_dd[1]:.2f}R")
    return res_df, ci_pf

def feature_stability(importances_list, features):
    imp_arr = np.array(importances_list)
    mean_imp = np.mean(imp_arr, axis=0)
    std_imp = np.std(imp_arr, axis=0)
    cv_imp = np.divide(std_imp, mean_imp, out=np.zeros_like(std_imp), where=mean_imp!=0)
    
    df = pd.DataFrame({
        'Feature': features,
        'Mean_Importance': mean_imp,
        'Std_Dev': std_imp,
        'CV': cv_imp
    }).sort_values(by='Mean_Importance', ascending=False)
    
    print("\nFeature Stability Across Folds:")
    print(df.to_string(index=False))
    return df

def run_robustness():
    os.makedirs("ml/reports", exist_ok=True)
    
    print("1. Preparing Datasets for ATR Sensitivity...")
    for atr in [1.8, 2.0, 2.2]:
        build_dataset(atr_multiplier=atr)
        
    config = {
        'max_depth': 2, 'learning_rate': 0.01, 'n_estimators': 100, 
        'subsample': 0.9, 'colsample_bytree': 0.9, 'reg_alpha': 0.1, 'reg_lambda': 10
    }
    
    print("\n2. Running Baseline Inference (ATR 2.0, Threshold 0.55)...")
    base_trades, importances, features = get_walk_forward_trades(
        "datasets/ml_volatility_expansion_atr_2_0.csv", 0.55, config, return_feature_importances=True
    )
    
    if base_trades.empty:
        print("No trades generated by baseline!")
        return
        
    print(f"Baseline Trades Collected: {len(base_trades)}")
    base_pf = calc_pf(base_trades['result_r'])
    print(f"Baseline PF: {base_pf:.3f}")
    
    auditor.export_csv("trade_log.csv", base_trades)
    
    mc_res = monte_carlo_simulation(base_trades)
    
    bs_res, ci_pf = bootstrap_analysis(base_trades)
    
    print("\n5. Sensitivity Analysis: Probability Threshold")
    for prob in [0.50, 0.53, 0.55, 0.57, 0.60]:
        trades = base_trades[base_trades['pred_prob'] >= prob]
        pf = calc_pf(trades['result_r']) if not trades.empty else 0.0
        print(f"Threshold {prob:.2f} -> Trades: {len(trades)}, PF: {pf:.3f}")
        
    print("\n6. Sensitivity Analysis: ATR Multiplier")
    atr_pfs = []
    for atr in [1.8, 2.0, 2.2]:
        str_atr = str(atr).replace('.', '_')
        trades = get_walk_forward_trades(f"datasets/ml_volatility_expansion_atr_{str_atr}.csv", 0.55, config)
        pf = calc_pf(trades['result_r']) if not trades.empty else 0.0
        atr_pfs.append(pf)
        print(f"ATR {atr} -> Trades: {len(trades)}, PF: {pf:.3f}")
        
    feature_stability(importances, features)
    
    print("\n=== V3.25 Acceptance Evaluation ===")
    med_mc_pf = mc_res['pf'].median()
    p95_mc_dd = mc_res['max_dd'].quantile(0.95)
    
    crit_1 = med_mc_pf > 1.2
    crit_2 = p95_mc_dd < 15.0
    crit_3 = ci_pf[0] > 1.0 
    
    print(f"1. MC Median PF > 1.2: {med_mc_pf:.3f} -> {'PASS' if crit_1 else 'FAIL'}")
    print(f"2. MC 95th Max DD < 15R: {p95_mc_dd:.2f}R -> {'PASS' if crit_2 else 'FAIL'}")
    print(f"3. Bootstrap Lower Bound > 1.0: {ci_pf[0]:.3f} -> {'PASS' if crit_3 else 'FAIL'}")
    
    passed = crit_1 and crit_2 and crit_3
    print(f"\nFinal Status: {'APPROVED FOR V4' if passed else 'REJECTED'}")
    
    with open("ml/reports/robustness_report.txt", "w") as f:
        f.write(f"MC Median PF: {med_mc_pf:.3f}\n")
        f.write(f"MC 95th Max DD: {p95_mc_dd:.2f}\n")
        f.write(f"Bootstrap 95% CI PF: {ci_pf[0]:.3f} to {ci_pf[1]:.3f}\n")
        f.write(f"Status: {'APPROVED' if passed else 'REJECTED'}\n")

if __name__ == "__main__":
    run_robustness()
