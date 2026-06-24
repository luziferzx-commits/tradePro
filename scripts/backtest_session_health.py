import pandas as pd
import numpy as np
import os
import sys
import logging

# Add parent directory to path to import risk module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from risk.session_health import AdaptiveSessionHealth

# Set up a file handler for transitions if requested
def setup_transition_logger(export_csv=False):
    logger = logging.getLogger("SessionHealth")
    # clear existing handlers
    logger.handlers = []
    
    if export_csv:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler('results/session_health_transitions_raw.log', mode='w')
        formatter = logging.Formatter('%(asctime)s,%(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    else:
        logger.setLevel(logging.WARNING)

def run_backtest(df_original, params, export_csv=False):
    setup_transition_logger(export_csv)
    
    df = df_original.copy()
    health_monitor = AdaptiveSessionHealth(
        rolling_window=params.get('rolling_window', 20),
        recovery_trades=params.get('recovery_trades', 10),
        disabled_threshold=params.get('disabled_threshold', 0.70),
        degraded_multiplier=params.get('degraded_multiplier', 0.60),
        warning_multiplier=params.get('warning_multiplier', 0.85)
    )
    
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
        
        risk_multiplier = health_monitor.get_risk_multiplier(features)
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
    
    windows = df['window_idx'].unique()
    adjusted_passing = 0
    window_stats = []
    
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
        
        window_stats.append({
            'window': w,
            'pf': a_pf,
            'max_dd': a_dd,
            'trades': taken_trades,
            'skipped': disabled_trades,
            'status': a_status
        })
        
    tot_trades = len(df)
    tot_taken = len(df[df['risk_multiplier'] > 0])
    tot_skipped = len(df[df['risk_multiplier'] == 0])
    tot_reduced = len(df[(df['risk_multiplier'] > 0) & (df['risk_multiplier'] < 1.0)])
    
    a_pf = df[df['real_pnl'] > 0]['real_pnl'].sum() / abs(df[df['real_pnl'] < 0]['real_pnl'].sum())
    skipped_pct = tot_skipped / tot_trades if tot_trades > 0 else 0
    
    asia_normal_opp_cost = df[df['context'] == 'Asia + NORMAL']['opportunity_cost'].sum()
    
    # Check hard filters: W1/W2/W4/W9 must remain PASS
    mandatory_windows = [1, 2, 4, 9]
    mandatory_pass = True
    for w_stat in window_stats:
        if w_stat['window'] in mandatory_windows and w_stat['status'] != 'PASS':
            mandatory_pass = False
            break
            
    # Max DD checks for W6/W8/W10
    worst_window_dd = 0
    w6_dd = w8_dd = w10_dd = 0
    for w_stat in window_stats:
        if w_stat['window'] == 6: w6_dd = w_stat['max_dd']
        if w_stat['window'] == 8: w8_dd = w_stat['max_dd']
        if w_stat['window'] == 10: w10_dd = w_stat['max_dd']
        if w_stat['max_dd'] < worst_window_dd:
            worst_window_dd = w_stat['max_dd']
            
    # Build results dict
    metrics = {
        'params': params,
        'passing_windows': adjusted_passing,
        'overall_pf': a_pf,
        'skipped_pct': skipped_pct,
        'skipped_trades': tot_skipped,
        'mandatory_pass': mandatory_pass,
        'worst_dd': worst_window_dd,
        'w6_dd': w6_dd,
        'w8_dd': w8_dd,
        'w10_dd': w10_dd,
        'asia_normal_opp_cost': asia_normal_opp_cost
    }
    
    if export_csv:
        # Export summary
        summary_df = pd.DataFrame(window_stats)
        summary_df.to_csv('results/session_health_summary.csv', index=False)
        
        # Export Contexts
        ctx_df = df.groupby('context').agg(
            total_trades=('context', 'count'),
            skipped_trades=('risk_multiplier', lambda x: (x == 0).sum()),
            saved_loss=('saved_loss', 'sum'),
            opportunity_cost=('opportunity_cost', 'sum')
        ).reset_index()
        ctx_df.to_csv('results/session_health_contexts.csv', index=False)
        
        # Export opportunity cost deep dive
        opp_df = df[df['opportunity_cost'] > 0].copy()
        opp_df.to_csv('results/session_health_opportunity_cost.csv', index=True)
        
        # Close logging handlers to release file lock
        for handler in logging.getLogger("SessionHealth").handlers:
            handler.close()
            
        # Transitions are logged to raw log, let's parse it to CSV
        try:
            with open('results/session_health_transitions_raw.log', 'r') as f:
                lines = f.readlines()
            transitions = []
            for line in lines:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    ts = parts[0]
                    msg = parts[1]
                    transitions.append({'timestamp': ts, 'message': msg})
            trans_df = pd.DataFrame(transitions)
            trans_df.to_csv('results/session_health_transitions.csv', index=False)
            os.remove('results/session_health_transitions_raw.log')
        except Exception as e:
            print("Error parsing transitions log:", e)
            
        print(f"Exported diagnostics to results/session_health_*.csv")
        
    return metrics

def run_baseline_export():
    try:
        df = pd.read_csv('results/context_preds.csv', parse_dates=['time'])
    except Exception as e:
        print("Could not load CSV.")
        return
        
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    
    params = {
        'rolling_window': 15,
        'recovery_trades': 5,
        'disabled_threshold': 0.50,
        'degraded_multiplier': 0.60,
        'warning_multiplier': 0.85
    }
    print("Running Candidate V2 Baseline and exporting diagnostics...")
    metrics = run_backtest(df, params, export_csv=True)
    print("Baseline Metrics:", metrics)

if __name__ == "__main__":
    run_baseline_export()
