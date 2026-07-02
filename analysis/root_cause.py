import os
import json
import yaml
import pandas as pd
import numpy as np
from datetime import datetime

def calc_metrics(g):
    wins = g[g['result'] == 'WIN']
    losses = g[g['result'] == 'LOSS']
    gross_profit = wins['pnl'].sum()
    gross_loss = abs(losses['pnl'].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else 99.0
    win_rate = len(wins) / len(g) * 100 if len(g) > 0 else 0
    
    cum_pnl = g['pnl'].cumsum()
    peak = cum_pnl.cummax()
    dd = peak - cum_pnl
    max_dd = dd.max()
    
    r_mults = g['r_multiple']
    exp_r = r_mults.mean() if not r_mults.empty else 0.0
    median_r = r_mults.median() if not r_mults.empty else 0.0
    avg_rr = r_mults[r_mults > 0].mean() if not r_mults[r_mults > 0].empty else 0.0
    
    max_single_trade_r = r_mults.max() if not r_mults.empty else 0.0
    total_r_profit = r_mults[r_mults > 0].sum()
    outlier_score = max_single_trade_r / total_r_profit if total_r_profit > 0 else 0.0

    return pd.Series({
        'Trades': len(g),
        'PF': pf,
        'Exp_R': exp_r,
        'Median_R': median_r,
        'WinRate': win_rate,
        'AvgRR': avg_rr,
        'MaxDD': max_dd,
        'Max_1Trade_R': max_single_trade_r,
        'Outlier_Dep': outlier_score
    })

def calc_stability(df_group):
    # Splits chronologically into 5 chunks and calculates cumulative PF at each chunk
    if len(df_group) < 10:
        return [0.0]*5
    
    df_sorted = df_group.sort_values('entry_time_utc')
    chunk_size = max(1, len(df_sorted) // 5)
    
    pfs = []
    for i in range(1, 6):
        end_idx = min(i * chunk_size, len(df_sorted))
        if i == 5: end_idx = len(df_sorted)
        chunk = df_sorted.iloc[:end_idx]
        wins = chunk[chunk['result'] == 'WIN']
        losses = chunk[chunk['result'] == 'LOSS']
        g_profit = wins['pnl'].sum()
        g_loss = abs(losses['pnl'].sum())
        pfs.append(g_profit / g_loss if g_loss > 0 else 99.0)
    return pfs

def get_stability_verdict(pfs, trades):
    if trades < 30: return "INSUFFICIENT_SAMPLE"
    
    # Check if PF crashes heavily at the end
    max_pf = max(pfs)
    final_pf = pfs[-1]
    
    if final_pf < 1.0: return "UNSTABLE"
    if max_pf > 1.5 and final_pf < 1.1: return "DECAYING"
    
    # Calculate volatility of PF progression (ignoring the 99.0 outliers if zero losses early)
    valid_pfs = [p for p in pfs if p < 50.0]
    if len(valid_pfs) > 1 and np.std(valid_pfs) > 1.0:
        return "HIGH_VARIANCE"
        
    return "STABLE"

def format_table(df_agg):
    return df_agg.round(2).to_markdown()

def generate_market_intelligence_report(df_trades, base_dir):
    report_path = os.path.join(base_dir, "reports", "MARKET_INTELLIGENCE_REPORT.md")
    
    if df_trades.empty:
        with open(report_path, 'w') as f:
            f.write("# Market Intelligence Report\nNo trades executed.")
        return

    # Bucketization
    df_trades['ATR_Bucket'] = df_trades.groupby('symbol')['atr'].transform(
        lambda x: pd.qcut(x, 4, labels=['Low', 'Medium', 'High', 'Extreme'], duplicates='drop') if len(x.unique()) > 4 else 'Medium'
    )
    bins = [-1, 20, 25, 40, 100]
    labels = ['Weak (<20)', 'Rising (20-25)', 'Strong (25-40)', 'Extreme (>40)']
    df_trades['ADX_Bucket'] = pd.cut(df_trades['adx'], bins=bins, labels=labels)
    
    tbins = [-999, -1, -0.2, 0.2, 1, 999]
    tlabels = ['Strong Down', 'Down', 'Flat', 'Up', 'Strong Up']
    df_trades['Trend_Bucket'] = pd.cut(df_trades['ema50_slope'], bins=tbins, labels=tlabels)

    engine_stats = df_trades.groupby('engine').apply(calc_metrics).reset_index()
    df_abc = df_trades[df_trades['engine'] == 'ABC+Session'].copy()
    if df_abc.empty:
        df_abc = df_trades

    # Market DNA
    dna_dict = {}
    symbols = df_abc['symbol'].unique()
    for sym in symbols:
        df_sym = df_abc[df_abc['symbol'] == sym]
        if df_sym.empty: continue
        best_session = df_sym.groupby('session')['pnl'].sum().idxmax()
        best_strat = df_sym.groupby('strategy')['pnl'].sum().idxmax()
        best_regime = df_sym.groupby('regime')['pnl'].sum().idxmax()
        if 'ATR_Bucket' in df_sym and not df_sym['ATR_Bucket'].isnull().all():
            best_atr = df_sym.groupby('ATR_Bucket', observed=False)['pnl'].sum().idxmax()
        else:
            best_atr = "Medium"
        dna_dict[sym] = {
            "best_session": str(best_session),
            "core_strategy": str(best_strat),
            "preferred_regime": str(best_regime),
            "optimal_volatility": str(best_atr)
        }

    # Heatmap
    heatmap = pd.pivot_table(df_abc, values='pnl', index='symbol', columns='session', aggfunc=lambda x: x[x>0].sum() / abs(x[x<0].sum()) if abs(x[x<0].sum())>0 else 99)

    # Time Robustness (Yearly PF)
    if 'year' in df_abc.columns:
        yearly_impact = df_abc.groupby('year').apply(calc_metrics).reset_index()
    else:
        yearly_impact = pd.DataFrame()

    # Knowledge Extraction / Rules Generation
    pattern_cols = ['symbol', 'session', 'strategy', 'regime', 'ATR_Bucket', 'ADX_Bucket']
    
    router_rules = {}
    rejected_rules = []
    winning_json = []
    
    grouped = df_abc.groupby(pattern_cols, observed=False)
    
    stability_records = []
    
    for name, group in grouped:
        if group.empty: continue
        metrics = calc_metrics(group)
        trades = metrics['Trades']
        pf = metrics['PF']
        expr = metrics['Exp_R']
        outlier = metrics['Outlier_Dep']
        
        # Stability
        pfs = calc_stability(group)
        verdict = get_stability_verdict(pfs, trades)
        
        record = {
            "symbol": name[0],
            "session": name[1],
            "strategy": name[2],
            "regime": name[3],
            "atr_bucket": name[4],
            "adx_bucket": name[5],
            "trades": float(trades),
            "pf": float(pf),
            "exp_r": float(expr),
            "outlier_dep": float(outlier),
            "verdict": verdict,
            "pfs_progression": [round(p, 2) for p in pfs]
        }
        
        if trades >= 30:
            stability_records.append(record)
        
        # Rule Filters
        if pf >= 1.20 and expr > 0 and trades >= 30 and outlier <= 0.35 and verdict in ["STABLE", "HIGH_VARIANCE"]:
            winning_json.append(record)
            
            sym = name[0]
            sess = name[1]
            if sym not in router_rules:
                router_rules[sym] = {}
            if sess not in router_rules[sym]:
                # If multiple strategies pass, pick the highest PF
                router_rules[sym][sess] = {
                    "preferred_strategy": name[2],
                    "allowed_regimes": [name[3]],
                    "atr_bucket": name[4],
                    "adx_bucket": name[5],
                    "historical_pf": float(pf),
                    "expectancy_r": float(expr),
                    "trade_count": int(trades),
                    "stability_verdict": verdict,
                    "confidence_score": float(min(0.99, round(1 - outlier, 2))),
                    "promotion_status": "RESEARCH_VALIDATED",
                    "shadow_passed": False,
                    "live_passed": False,
                    "source_report": "MARKET_INTELLIGENCE_REPORT_V2",
                    "generated_at": datetime.now().isoformat()
                }
            else:
                # Compare PF
                if pf > router_rules[sym][sess]['historical_pf']:
                    router_rules[sym][sess]["preferred_strategy"] = name[2]
                    router_rules[sym][sess]["allowed_regimes"] = [name[3]]
                    router_rules[sym][sess]["atr_bucket"] = name[4]
                    router_rules[sym][sess]["historical_pf"] = float(pf)
                    router_rules[sym][sess]["confidence_score"] = float(min(0.99, round(1 - outlier, 2)))
        else:
            if trades >= 30:
                reason = []
                if pf < 1.20: reason.append("Low PF")
                if expr <= 0: reason.append("Negative EV")
                if outlier > 0.35: reason.append("Outlier Dependency")
                if verdict not in ["STABLE", "HIGH_VARIANCE"]: reason.append(f"Verdict: {verdict}")
                record['reason'] = ", ".join(reason)
                rejected_rules.append(record)

    # Save JSON files
    k_dir = os.path.join(base_dir, "knowledge")
    os.makedirs(k_dir, exist_ok=True)
    with open(os.path.join(k_dir, "market_dna.json"), "w") as f: json.dump(dna_dict, f, indent=2)
    with open(os.path.join(k_dir, "winning_patterns.json"), "w") as f: json.dump(winning_json, f, indent=2)
    with open(os.path.join(k_dir, "losing_patterns.json"), "w") as f: json.dump(rejected_rules, f, indent=2)
    
    r_dir = os.path.join(base_dir, "generated_rules")
    os.makedirs(r_dir, exist_ok=True)
    with open(os.path.join(r_dir, "router_rules.yaml"), "w") as f: yaml.dump(router_rules, f, sort_keys=False)

    df_stability = pd.DataFrame(stability_records)

    content = f"""# Market Intelligence Report
*Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*

> [!WARNING]
> **RESEARCH_EXECUTION_MODEL = candle_close_fill**
> `spread_model = SIMULATED_DYNAMIC_ATR_BASED`.

## 1. Engine Benchmark
{format_table(engine_stats)}

## 2. Time Robustness (Yearly Impact)
{format_table(yearly_impact) if not yearly_impact.empty else "No yearly data"}

## 3. Stability Test (Progressive Chunks)
{format_table(df_stability[['symbol', 'session', 'strategy', 'trades', 'pf', 'verdict', 'pfs_progression']].head(20)) if not df_stability.empty else "No pattern reached 30 trades for stability testing."}

## 4. Market DNA Profiles
"""
    for sym, dna in dna_dict.items():
        content += f"### {sym}\n- **Best Session**: {dna['best_session']}\n- **Core Strategy**: {dna['core_strategy']}\n- **Optimal Volatility**: {dna['optimal_volatility']}\n"
    
    content += f"""
## 5. Symbol × Session Profit Factor Heatmap
{heatmap.round(2).to_markdown() if not heatmap.empty else "No data"}

## 6. Knowledge Extraction Summary
- Successfully exported `knowledge/market_dna.json`
- Successfully exported `knowledge/winning_patterns.json`
- Successfully exported `generated_rules/router_rules.yaml`

### Generated Router Rules (Passed Filters)
```yaml
{yaml.dump(router_rules, sort_keys=False) if router_rules else "No combinations passed the strict filters (PF >= 1.20, EV > 0, Trades >= 30, Outlier <= 0.35, Stable)"}
```

### Top Rejected Rules (Failed Filters but had volume)
"""
    if rejected_rules:
        df_rej = pd.DataFrame(rejected_rules).sort_values('pf', ascending=False).head(10)
        content += format_table(df_rej[['symbol', 'session', 'strategy', 'trades', 'pf', 'verdict', 'reason']])
    else:
        content += "None."

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Market Intelligence Report generated at {report_path}")

if __name__ == '__main__':
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    csv_path = os.path.join(base_dir, "results", "research_backtest_v2_trades.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        generate_market_intelligence_report(df, base_dir)
    else:
        print("No trade data found. Please run research_backtest_v2.py first.")
