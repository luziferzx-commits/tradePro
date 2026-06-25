import pandas as pd
import numpy as np

def diagnose_atr():
    print("Loading predictions from results/context_preds.csv...")
    try:
        df = pd.read_csv('results/context_preds.csv', parse_dates=['time'])
    except Exception as e:
        print("Could not load CSV. Please run the walk forward script first.")
        return
        
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    
    trades = len(df)
    if trades == 0:
        print("No trades found.")
        return
        
    # We will use the 'vol_percentile' column if it accurately reflects ATR percentile,
    # or calculate the global ATR percentile across all trades just to be sure.
    # The user asked for "ATR percentile", so let's calculate the percentile of 'atr'
    # across the entire dataset of trades.
    
    # Calculate global ATR percentiles
    p50 = df['atr'].quantile(0.50)
    p75 = df['atr'].quantile(0.75)
    p90 = df['atr'].quantile(0.90)
    p95 = df['atr'].quantile(0.95)
    
    print(f"\nTotal Trades: {trades}")
    print(f"Global ATR distribution:")
    print(f"50th Percentile: {p50:.5f}")
    print(f"75th Percentile: {p75:.5f}")
    print(f"90th Percentile: {p90:.5f}")
    print(f"95th Percentile: {p95:.5f}")
    print("-" * 50)
    
    # Create bins
    conditions = [
        df['atr'] <= p50,
        (df['atr'] > p50) & (df['atr'] <= p75),
        (df['atr'] > p75) & (df['atr'] <= p90),
        df['atr'] > p90
    ]
    choices = ['1. < 50%', '2. 50% - 75%', '3. 75% - 90%', '4. > 90%']
    df['atr_bucket'] = np.select(conditions, choices, default='Unknown')
    
    print("\n--- Overall PF by ATR Percentile (All Windows) ---")
    overall_stats = df.groupby('atr_bucket').agg(
        Trades=('target_sell', 'count'),
        Wins=('target_sell', 'sum')
    )
    overall_stats['Losses'] = overall_stats['Trades'] - overall_stats['Wins']
    overall_stats['Win Rate'] = (overall_stats['Wins'] / overall_stats['Trades']) * 100
    overall_stats['PF'] = (overall_stats['Wins'] * 1.5) / (overall_stats['Losses'].replace(0, 1) * 1.0)
    print(overall_stats.to_string())
    
    # Let's also look at specific failing windows
    failing_windows = [6, 8, 10]
    passing_windows = [1, 2, 4, 9]
    
    for group_name, windows in [("FAILING WINDOWS (W6, W8, W10)", failing_windows), ("PASSING WINDOWS (W1, W2, W4, W9)", passing_windows)]:
        print(f"\n\n==================================================")
        print(f"--- PF by ATR Percentile in {group_name} ---")
        w_df = df[df['window_idx'].isin(windows)].copy()
        
        stats = w_df.groupby('atr_bucket').agg(
            Trades=('target_sell', 'count'),
            Wins=('target_sell', 'sum')
        )
        stats['Losses'] = stats['Trades'] - stats['Wins']
        stats['Win Rate'] = (stats['Wins'] / stats['Trades']) * 100
        stats['PF'] = (stats['Wins'] * 1.5) / (stats['Losses'].replace(0, 1) * 1.0)
        print(stats.to_string())
        
    print(f"\n==================================================")
    print("--- Let's do a strict test on ATR > 90% vs ATR <= 90% across ALL windows ---")
    
    high_vol = df[df['atr'] > p90]
    normal_vol = df[df['atr'] <= p90]
    
    high_pf = (high_vol['target_sell'].sum() * 1.5) / ((len(high_vol) - high_vol['target_sell'].sum()) * 1.0) if len(high_vol) > 0 else 0
    norm_pf = (normal_vol['target_sell'].sum() * 1.5) / ((len(normal_vol) - normal_vol['target_sell'].sum()) * 1.0) if len(normal_vol) > 0 else 0
    
    print(f"ATR > 90% PF : {high_pf:.2f} (Trades: {len(high_vol)}, Win Rate: {(high_vol['target_sell'].sum() / len(high_vol) * 100) if len(high_vol) > 0 else 0:.1f}%)")
    print(f"ATR <= 90% PF: {norm_pf:.2f} (Trades: {len(normal_vol)}, Win Rate: {(normal_vol['target_sell'].sum() / len(normal_vol) * 100) if len(normal_vol) > 0 else 0:.1f}%)")

if __name__ == "__main__":
    diagnose_atr()
