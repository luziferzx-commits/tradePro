import pandas as pd
import itertools
import sys
import os

# Ensure we can import scripts.backtest_session_health
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.backtest_session_health import run_backtest

def run_sweep():
    print("Loading predictions from results/context_preds.csv...")
    try:
        df = pd.read_csv('results/context_preds.csv', parse_dates=['time'])
    except Exception as e:
        print("Could not load CSV.")
        return
        
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    
    # Define hyperparameter grid
    param_grid = {
        'rolling_window': [15, 20, 30],
        'recovery_trades': [5, 10, 15],
        'disabled_threshold': [0.64, 0.50],
        'degraded_multiplier': [0.60, 0.70],
        'warning_multiplier': [0.85, 0.90]
    }
    
    # Generate all combinations
    keys, values = zip(*param_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    total_runs = len(combinations)
    print(f"Starting parameter sweep with {total_runs} combinations...")
    
    results = []
    
    for i, params in enumerate(combinations):
        if (i+1) % 10 == 0:
            print(f"Running combination {i+1}/{total_runs}...")
        
        # Suppress logging by NOT setting export_csv
        metrics = run_backtest(df, params, export_csv=False)
        results.append(metrics)
        
    print("\n--- Sweeping Complete. Filtering results ---")
    
    # 1. Apply Hard Filters
    passed_filters = []
    for res in results:
        if res['passing_windows'] >= 7 and \
           res['overall_pf'] >= 1.60 and \
           res['mandatory_pass'] and \
           res['skipped_pct'] <= 0.35:
           
           # Check if W6/W8/W10 max DD is materially lower than baseline
           # Baseline DD: W6 ~ -14.5, W8 ~ -22.5, W10 ~ -19.0
           # We define materially lower as > -12R for all three.
           if res['w6_dd'] >= -12.0 and res['w8_dd'] >= -12.0 and res['w10_dd'] >= -12.0:
               passed_filters.append(res)
               
    print(f"Combinations passing all hard filters: {len(passed_filters)} / {total_runs}")
    
    if len(passed_filters) == 0:
        print("No combinations passed the strict filters! We will show the best from all.")
        passed_filters = results
        
    # 2. Ranking
    # Ranking criteria priority:
    # 1. Lowest worst-window Max DD (descending, because closer to 0 is better, e.g., -5 > -10)
    # 2. Lowest skipped trades % (ascending)
    # 3. Lowest Asia + NORMAL opportunity cost (ascending)
    # 4. Highest Overall PF (descending)
    # 5. Highest Passing Windows count (descending)
    
    def sort_key(r):
        return (
            r['worst_dd'],               # 1. Highest is best (closest to 0)
            -r['skipped_pct'],           # 2. Lowest skipped % is best (negative to sort descending)
            -r['asia_normal_opp_cost'],  # 3. Lowest opp cost is best (negative to sort descending)
            r['overall_pf'],             # 4. Highest PF is best
            r['passing_windows']         # 5. Highest count is best
        )
        
    passed_filters.sort(key=sort_key, reverse=True)
    
    print("\n--- Top 5 Configurations ---")
    for i, res in enumerate(passed_filters[:5]):
        print(f"\nRank {i+1}:")
        print(f"Parameters: {res['params']}")
        print(f"Passing Windows: {res['passing_windows']}/10")
        print(f"Overall PF: {res['overall_pf']:.2f}")
        print(f"Skipped Trades: {res['skipped_pct']*100:.1f}% ({res['skipped_trades']} trades)")
        print(f"Worst Max DD: {res['worst_dd']:.1f}R (W6: {res['w6_dd']:.1f}R, W8: {res['w8_dd']:.1f}R, W10: {res['w10_dd']:.1f}R)")
        print(f"Asia+NORMAL Opportunity Cost: {res['asia_normal_opp_cost']:.1f}R")
        print("---")

    # Export all results for analysis
    flat_results = []
    for r in results:
        flat = r['params'].copy()
        flat.update({k:v for k,v in r.items() if k != 'params'})
        flat_results.append(flat)
    
    pd.DataFrame(flat_results).to_csv('results/session_health_sweep_all.csv', index=False)
    print("Exported all sweep results to results/session_health_sweep_all.csv")

if __name__ == "__main__":
    run_sweep()
