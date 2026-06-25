import os
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

def format_table(df_agg):
    return df_agg.round(2).to_markdown()

def get_failure_recommendation(row):
    recs = []
    if row['PF'] < 1.0:
        if row.name[4] == 'Low': # ATR Low
            recs.append("Disable in low volatility.")
        if row.name[5] in ['Weak', 'Rising']: # ADX
            recs.append("Requires stronger momentum.")
        if row['Outlier_Dep'] > 0.5:
            recs.append("Highly unstable, profit relies on luck.")
    if not recs:
        recs.append("Review strategy parameters.")
    return " ".join(recs)

def generate_market_intelligence_report(df_trades, report_path):
    if df_trades.empty:
        with open(report_path, 'w') as f:
            f.write("# Market Intelligence Report\nNo trades executed.")
        return

    # Bucketization
    # ATR bucket per symbol to make it relative
    df_trades['ATR_Bucket'] = df_trades.groupby('symbol')['atr'].transform(
        lambda x: pd.qcut(x, 4, labels=['Low', 'Medium', 'High', 'Extreme'], duplicates='drop') if len(x.unique()) > 4 else 'Medium'
    )
    
    # ADX Bucket
    bins = [-1, 20, 25, 40, 100]
    labels = ['Weak (<20)', 'Rising (20-25)', 'Strong (25-40)', 'Extreme (>40)']
    df_trades['ADX_Bucket'] = pd.cut(df_trades['adx'], bins=bins, labels=labels)
    
    # Trend Bucket (EMA50 Slope)
    tbins = [-999, -1, -0.2, 0.2, 1, 999]
    tlabels = ['Strong Down', 'Down', 'Flat', 'Up', 'Strong Up']
    df_trades['Trend_Bucket'] = pd.cut(df_trades['ema50_slope'], bins=tbins, labels=tlabels)

    engine_stats = df_trades.groupby('engine').apply(calc_metrics).reset_index()

    df_abc = df_trades[df_trades['engine'] == 'ABC+Session'].copy()
    if df_abc.empty:
        df_abc = df_trades

    # Market DNA
    dna_lines = []
    symbols = df_abc['symbol'].unique()
    for sym in symbols:
        df_sym = df_abc[df_abc['symbol'] == sym]
        if df_sym.empty: continue
        best_session = df_sym.groupby('session')['pnl'].sum().idxmax()
        best_strat = df_sym.groupby('strategy')['pnl'].sum().idxmax()
        best_regime = df_sym.groupby('regime')['pnl'].sum().idxmax()
        best_atr = df_sym.groupby('ATR_Bucket', observed=False)['pnl'].sum().idxmax()
        dna_lines.append(f"### {sym}\n- **Best Session**: {best_session}\n- **Core Strategy**: {best_strat}\n- **Regime**: {best_regime}\n- **Optimal Volatility**: {best_atr} ATR\n")

    # Heatmap
    heatmap = pd.pivot_table(df_abc, values='pnl', index='symbol', columns='session', aggfunc=lambda x: x[x>0].sum() / abs(x[x<0].sum()) if abs(x[x<0].sum())>0 else 99)

    # Feature Impacts
    atr_impact = df_abc.groupby('ATR_Bucket', observed=False).apply(calc_metrics).reset_index()
    adx_impact = df_abc.groupby('ADX_Bucket', observed=False).apply(calc_metrics).reset_index()
    trend_impact = df_abc.groupby('Trend_Bucket', observed=False).apply(calc_metrics).reset_index()

    # Patterns
    pattern_cols = ['symbol', 'session', 'strategy', 'regime', 'ATR_Bucket', 'ADX_Bucket']
    patterns = df_abc.groupby(pattern_cols, observed=False).apply(calc_metrics)
    
    # Filter valid patterns
    valid_patterns = patterns[patterns['Trades'] >= 30].copy()
    
    if not valid_patterns.empty:
        valid_patterns = valid_patterns.sort_values('PF', ascending=False)
        top_20 = valid_patterns.head(20).reset_index()
        bottom_20 = valid_patterns.tail(20).sort_values('PF', ascending=True)
        bottom_20['Recommendation'] = bottom_20.apply(get_failure_recommendation, axis=1)
        bottom_20 = bottom_20.reset_index()
    else:
        top_20 = pd.DataFrame()
        bottom_20 = pd.DataFrame()

    content = f"""# Market Intelligence Report
*Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*

> [!WARNING]
> **RESEARCH_EXECUTION_MODEL = candle_close_fill**
> This report uses a simplified execution model for edge-discovery. 
> `spread_model = SIMULATED_DYNAMIC_ATR_BASED` (`spread_is_simulated = True`). This is NOT broker-real spread data.

## 1. Engine Benchmark
{format_table(engine_stats)}

## 2. Market DNA Profiles
"""
    content += "\n".join(dna_lines)
    
    content += f"""
## 3. Symbol × Session Profit Factor Heatmap
{heatmap.round(2).to_markdown() if not heatmap.empty else "No data"}

## 4. Feature Impact Analysis
### By ATR (Volatility)
{format_table(atr_impact)}

### By ADX (Momentum)
{format_table(adx_impact)}

### By Trend (EMA50 Slope)
{format_table(trend_impact)}

## 5. Top 20 Winning Patterns (Min 30 Trades)
*Identified strong edges in the market structure.*
{format_table(top_20) if not top_20.empty else "No patterns reached 30 trades yet."}

## 6. Top 20 Losing Patterns & Failure Analysis (Min 30 Trades)
*Identified leaks in the strategy execution.*
{format_table(bottom_20) if not bottom_20.empty else "No patterns reached 30 trades yet."}
"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Market Intelligence Report generated at {report_path}")

if __name__ == '__main__':
    csv_path = os.path.join(os.path.dirname(__file__), "..", "results", "research_backtest_v2_trades.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        generate_market_intelligence_report(df, os.path.join(os.path.dirname(__file__), "..", "reports", "MARKET_INTELLIGENCE_REPORT.md"))
    else:
        print("No trade data found. Please run research_backtest_v2.py first.")
