import pandas as pd
import numpy as np

def diagnose():
    print("Loading predictions from results/context_preds.csv...")
    try:
        df = pd.read_csv('results/context_preds.csv', parse_dates=['time'])
    except Exception as e:
        print("Could not load CSV. Running walk_forward_context.py first...")
        import walk_forward_context
        walk_forward_context.run_context_walk_forward()
        df = pd.read_csv('results/context_preds.csv', parse_dates=['time'])
        
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    
    windows = [1, 2, 4, 6, 8, 9, 10]
    
    for w in windows:
        w_df = df[df['window_idx'] == w].copy()
        if len(w_df) == 0:
            print(f"\nNo data for Window {w}")
            continue
            
        start_date = w_df.index.min()
        end_date = w_df.index.max()
        
        trades = len(w_df)
        wins = w_df['target_sell'].sum()
        losses = trades - wins
        
        gross_profit = wins * 1.5
        gross_loss = losses * 1.0
        pf = gross_profit / gross_loss if gross_loss > 0 else 999.0
        
        # Max consecutive loss
        w_df['is_loss'] = (w_df['target_sell'] == 0).astype(int)
        consecutive_losses = w_df['is_loss'].groupby((w_df['is_loss'] != w_df['is_loss'].shift()).cumsum()).sum()
        max_consecutive_loss = consecutive_losses.max()
        
        print(f"\n==================================================")
        print(f"WINDOW {w} DIAGNOSIS")
        print(f"Date Range: {start_date} to {end_date}")
        print(f"Total Trades: {trades} | Overall PF: {pf:.2f} | Max Consecutive Loss: {max_consecutive_loss}")
        print(f"Average Edge Score: {w_df['sell_edge_score'].mean():.2f}")
        print(f"Average ATR: {w_df['atr'].mean():.5f}")
        print(f"Average Volatility Percentile: {w_df['vol_percentile'].mean():.2f}%")
        
        print("\n--- Trades by Session ---")
        session_stats = w_df.groupby('session').agg(
            Trades=('target_sell', 'count'),
            Wins=('target_sell', 'sum')
        )
        session_stats['Losses'] = session_stats['Trades'] - session_stats['Wins']
        session_stats['PF'] = (session_stats['Wins'] * 1.5) / (session_stats['Losses'].replace(0, 1) * 1.0)
        print(session_stats.to_string())
        
        print("\n--- Trades by Market Regime ---")
        regime_stats = w_df.groupby('market_regime').agg(
            Trades=('target_sell', 'count'),
            Wins=('target_sell', 'sum')
        )
        regime_stats['Losses'] = regime_stats['Trades'] - regime_stats['Wins']
        regime_stats['PF'] = (regime_stats['Wins'] * 1.5) / (regime_stats['Losses'].replace(0, 1) * 1.0)
        print(regime_stats.to_string())
        
        print("\n--- Trades by Session + Regime ---")
        w_df['session_regime'] = w_df['session'].astype(str) + " + " + w_df['market_regime'].astype(str)
        interaction_stats = w_df.groupby('session_regime').agg(
            Trades=('target_sell', 'count'),
            Wins=('target_sell', 'sum')
        )
        interaction_stats['Losses'] = interaction_stats['Trades'] - interaction_stats['Wins']
        interaction_stats['PF'] = (interaction_stats['Wins'] * 1.5) / (interaction_stats['Losses'].replace(0, 1) * 1.0)
        interaction_stats.sort_values('PF', ascending=False, inplace=True)
        print(interaction_stats.to_string())
        print(f"==================================================\n")

if __name__ == "__main__":
    diagnose()
