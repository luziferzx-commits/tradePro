import pandas as pd
import numpy as np
import os
import sys

# Add parent directory to path to import risk module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from risk.session_health import AdaptiveSessionHealth

def backtest():
    print("Loading predictions from results/context_preds.csv...")
    try:
        df = pd.read_csv('results/context_preds.csv', parse_dates=['time'])
    except Exception as e:
        print("Could not load CSV. Please run the walk forward script first.")
        return
        
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    
    # Initialize the Risk Layer
    health_monitor = AdaptiveSessionHealth()
    
    adjusted_pnls = []
    theoretical_pnls = []
    multipliers = []
    
    print("\nSimulating Adaptive Session Health Monitor chronologically...")
    
    for i, row in df.iterrows():
        # Prepare features for the risk layer
        features = {
            'symbol': 'XAUUSD', # Assuming XAUUSDm from earlier
            'session': row['session'],
            'market_regime': row['market_regime'],
            'direction': 'SELL' # The test is on sell signals
        }
        
        # 1. Evaluate health BEFORE applying the trade
        risk_multiplier = health_monitor.get_risk_multiplier(features)
        multipliers.append(risk_multiplier)
        
        # 2. Calculate actual trade outcome (theoretical 1R base)
        # Note: target_sell is 1 for win, 0 for loss
        # Win is 1.5R, Loss is -1.0R
        theoretical_pnl_r = 1.5 if row['target_sell'] == 1 else -1.0
        theoretical_pnls.append(theoretical_pnl_r)
        
        # 3. Apply risk multiplier for adjusted PnL
        adjusted_pnl_r = theoretical_pnl_r * risk_multiplier
        adjusted_pnls.append(adjusted_pnl_r)
        
        # 4. Update health AFTER the trade using raw/theoretical 1R PnL
        health_monitor.update_trade(features, theoretical_pnl_r)
        
    df['theoretical_pnl'] = theoretical_pnls
    df['risk_multiplier'] = multipliers
    df['adjusted_pnl'] = adjusted_pnls
    
    print("\n--- Backtest Results by Window ---")
    
    windows = df['window_idx'].unique()
    baseline_passing = 0
    adjusted_passing = 0
    
    baseline_results = []
    adjusted_results = []
    
    for w in sorted(windows):
        w_df = df[df['window_idx'] == w]
        trades = len(w_df)
        
        if trades == 0:
            continue
            
        # Baseline Stats
        b_wins = (w_df['theoretical_pnl'] > 0).sum()
        b_win_rate = b_wins / trades
        b_gross_profit = w_df[w_df['theoretical_pnl'] > 0]['theoretical_pnl'].sum()
        b_gross_loss = abs(w_df[w_df['theoretical_pnl'] < 0]['theoretical_pnl'].sum())
        b_pf = b_gross_profit / b_gross_loss if b_gross_loss > 0 else float('inf')
        
        b_cum_pnl = w_df['theoretical_pnl'].cumsum()
        b_peak = b_cum_pnl.cummax()
        # In actual money terms, but here we just use R
        b_dd = (b_cum_pnl - b_peak).min() # Max drawdown in R
        
        b_status = "PASS" if b_pf >= 1.6 and trades >= 30 else "FAIL" # Simplified status
        if b_status == "PASS": baseline_passing += 1
        
        # Adjusted Stats
        # Only count trades that were actually taken (multiplier > 0)
        taken_df = w_df[w_df['risk_multiplier'] > 0]
        taken_trades = len(taken_df)
        disabled_trades = trades - taken_trades
        
        if taken_trades > 0:
            a_wins = (taken_df['adjusted_pnl'] > 0).sum()
            a_win_rate = a_wins / taken_trades
            a_gross_profit = taken_df[taken_df['adjusted_pnl'] > 0]['adjusted_pnl'].sum()
            a_gross_loss = abs(taken_df[taken_df['adjusted_pnl'] < 0]['adjusted_pnl'].sum())
            a_pf = a_gross_profit / a_gross_loss if a_gross_loss > 0 else float('inf')
            
            a_cum_pnl = taken_df['adjusted_pnl'].cumsum()
            a_peak = a_cum_pnl.cummax()
            a_dd = (a_cum_pnl - a_peak).min() # Max drawdown in R
        else:
            a_win_rate = 0
            a_pf = 0
            a_dd = 0
            
        a_status = "PASS" if a_pf >= 1.6 and taken_trades >= 30 else "FAIL"
        if a_status == "PASS": adjusted_passing += 1
        
        print(f"\nWindow {w}:")
        print(f"  BASELINE: PF {b_pf:.2f} | WinRate {b_win_rate*100:.1f}% | Trades {trades} | Max DD {b_dd:.1f}R | Status {b_status}")
        print(f"  ADJUSTED: PF {a_pf:.2f} | WinRate {a_win_rate*100:.1f}% | Trades {taken_trades} (Skipped {disabled_trades}) | Max DD {a_dd:.1f}R | Status {a_status}")
        
    print("\n==================================================")
    print("--- OVERALL COMPARISON ---")
    
    tot_trades = len(df)
    tot_taken = len(df[df['risk_multiplier'] > 0])
    tot_skipped = len(df[df['risk_multiplier'] == 0])
    tot_reduced = len(df[(df['risk_multiplier'] > 0) & (df['risk_multiplier'] < 1.0)])
    
    b_pf = df[df['theoretical_pnl'] > 0]['theoretical_pnl'].sum() / abs(df[df['theoretical_pnl'] < 0]['theoretical_pnl'].sum())
    a_pf = df[df['adjusted_pnl'] > 0]['adjusted_pnl'].sum() / abs(df[df['adjusted_pnl'] < 0]['adjusted_pnl'].sum())
    
    b_winrate = (df['theoretical_pnl'] > 0).sum() / tot_trades
    a_winrate = (df[df['risk_multiplier'] > 0]['adjusted_pnl'] > 0).sum() / tot_taken if tot_taken > 0 else 0
    
    print(f"Total Trades: Baseline {tot_trades} -> Adjusted {tot_taken}")
    print(f"Skipped Trades (DISABLED): {tot_skipped}")
    print(f"Reduced Risk Trades (WARNING/DEGRADED): {tot_reduced}")
    print(f"Overall PF: Baseline {b_pf:.2f} -> Adjusted {a_pf:.2f}")
    print(f"Overall Win Rate: Baseline {b_winrate*100:.1f}% -> Adjusted {a_winrate*100:.1f}%")
    print(f"Passing Windows: Baseline {baseline_passing}/10 -> Adjusted {adjusted_passing}/10")
    
if __name__ == "__main__":
    backtest()
