import pandas as pd
import numpy as np
import os
import sys

# Add parent directory to path to import risk module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from risk.session_health import AdaptiveSessionHealth

def run_backtest(df_original, threshold_name, disabled_threshold):
    df = df_original.copy()
    health_monitor = AdaptiveSessionHealth()
    
    adjusted_pnls = []
    theoretical_pnls = []
    multipliers = []
    
    contexts = []
    
    for i, row in df.iterrows():
        features = {
            'symbol': 'XAUUSD',
            'session': row['session'],
            'market_regime': row['market_regime'],
            'direction': 'SELL'
        }
        
        context_str = f"{row['session']} + {row['market_regime']}"
        contexts.append(context_str)
        
        risk_multiplier = health_monitor.get_risk_multiplier(features, disabled_threshold=disabled_threshold)
        multipliers.append(risk_multiplier)
        
        theoretical_pnl_r = 1.5 if row['target_sell'] == 1 else -1.0
        theoretical_pnls.append(theoretical_pnl_r)
        
        adjusted_pnl_r = theoretical_pnl_r * risk_multiplier
        adjusted_pnls.append(adjusted_pnl_r)
        
        health_monitor.update_trade(features, theoretical_pnl_r)
        
    df['context'] = contexts
    df['theoretical_pnl'] = theoretical_pnls
    df['risk_multiplier'] = multipliers
    df['adjusted_pnl'] = adjusted_pnls
    
    # Shadow tracking
    df['shadow_pnl'] = df['theoretical_pnl']
    df['real_pnl'] = df['adjusted_pnl']
    df['opportunity_cost'] = np.maximum(df['shadow_pnl'] - df['real_pnl'], 0)
    df['saved_loss'] = np.maximum(df['real_pnl'] - df['shadow_pnl'], 0)
    
    print(f"\n==================================================")
    print(f"--- CANDIDATE {threshold_name} (DISABLED PF < {disabled_threshold}) ---")
    
    windows = df['window_idx'].unique()
    adjusted_passing = 0
    
    for w in sorted(windows):
        w_df = df[df['window_idx'] == w]
        trades = len(w_df)
        if trades == 0: continue
            
        taken_df = w_df[w_df['risk_multiplier'] > 0]
        taken_trades = len(taken_df)
        disabled_trades = trades - taken_trades
        
        if taken_trades > 0:
            a_wins = (taken_df['real_pnl'] > 0).sum()
            a_win_rate = a_wins / taken_trades
            a_gross_profit = taken_df[taken_df['real_pnl'] > 0]['real_pnl'].sum()
            a_gross_loss = abs(taken_df[taken_df['real_pnl'] < 0]['real_pnl'].sum())
            a_pf = a_gross_profit / a_gross_loss if a_gross_loss > 0 else float('inf')
            
            a_cum_pnl = taken_df['real_pnl'].cumsum()
            a_peak = a_cum_pnl.cummax()
            a_dd = (a_cum_pnl - a_peak).min()
        else:
            a_win_rate = 0; a_pf = 0; a_dd = 0
            
        a_status = "PASS" if a_pf >= 1.6 and taken_trades >= 30 else "FAIL"
        if a_status == "PASS": adjusted_passing += 1
        
        print(f"W{w:<2}: PF {a_pf:.2f} | Max DD {a_dd:>5.1f}R | Trades {taken_trades:>3} (Skip {disabled_trades:>3}) | {a_status}")
        
    tot_trades = len(df)
    tot_taken = len(df[df['risk_multiplier'] > 0])
    tot_skipped = len(df[df['risk_multiplier'] == 0])
    tot_reduced = len(df[(df['risk_multiplier'] > 0) & (df['risk_multiplier'] < 1.0)])
    
    a_pf = df[df['real_pnl'] > 0]['real_pnl'].sum() / abs(df[df['real_pnl'] < 0]['real_pnl'].sum())
    a_winrate = (df[df['risk_multiplier'] > 0]['real_pnl'] > 0).sum() / tot_taken if tot_taken > 0 else 0
    
    print(f"\nOverall PF: {a_pf:.2f}")
    print(f"Passing Windows: {adjusted_passing}/10")
    print(f"Skipped Trades: {tot_skipped}/{tot_trades} ({(tot_skipped/tot_trades)*100:.1f}%)")
    
    print("\n--- Diagnostics ---")
    skipped_by_session = df[df['risk_multiplier'] == 0].groupby('session').size()
    print("Skipped by Session:\n", skipped_by_session.to_string())
    
    print("\nTop 5 Contexts saving drawdown (Saved Loss):")
    saved_loss_ctx = df.groupby('context')['saved_loss'].sum().sort_values(ascending=False).head(5)
    print(saved_loss_ctx.to_string())
    
    print("\nTop 5 Contexts causing Opportunity Cost:")
    opp_cost_ctx = df.groupby('context')['opportunity_cost'].sum().sort_values(ascending=False).head(5)
    print(opp_cost_ctx.to_string())
    
def backtest():
    try:
        df = pd.read_csv('results/context_preds.csv', parse_dates=['time'])
    except Exception as e:
        print("Could not load CSV. Please run the walk forward script first.")
        return
        
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    
    # Baseline logging is suppressed for brevity since we're comparing thresholds
    run_backtest(df, "V2A", 0.75)
    run_backtest(df, "V2B", 0.70)
    
if __name__ == "__main__":
    import logging
    logger = logging.getLogger("SessionHealth")
    logger.setLevel(logging.WARNING) # Mute the verbose logging for backtest summary
    backtest()
