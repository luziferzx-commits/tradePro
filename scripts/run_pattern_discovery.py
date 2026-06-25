import os
import sys
import argparse
import pandas as pd
import numpy as np
import logging
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from market.session_detector import SessionDetector
from research.universal_feature_store import UniversalFeatureStore
from research.universal_outcome_store import UniversalOutcomeStore
from research.pattern_database import PatternDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("PatternDiscovery")

def get_regime(row):
    if pd.isna(row['ema50']) or pd.isna(row['ema200']): return "RANGE"
    if row['ema50'] > row['ema200'] and row['adx'] > 25: return "TREND"
    if row['ema50'] < row['ema200'] and row['adx'] > 25: return "TREND"
    return "RANGE"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candles", type=int, default=2000)
    parser.add_argument("--symbols", type=str, nargs='+', default=["XAUUSD"])
    parser.add_argument("--sl_mult", type=float, default=1.0)
    parser.add_argument("--tp_mult", type=float, default=1.5)
    args = parser.parse_args()

    if not mt5_client.connect():
        logger.error("Failed to connect to MT5.")
        return

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    all_outcomes = []
    
    total_features_saved = 0
    total_outcomes_saved = 0

    for symbol in args.symbols:
        logger.info(f"Processing {symbol} for Pattern Discovery...")
        df = mt5_client.get_historical_data(symbol, "M15", args.candles)
        if df.empty:
            logger.warning(f"No data for {symbol}, skipping.")
            continue
            
        logger.info("  Calculating base indicators...")
        df = IndicatorCalculator.add_indicators(df)
        
        logger.info("  Extracting regimes and sessions...")
        df['regime'] = df.apply(get_regime, axis=1)
        df['session_label'] = df['time'].apply(lambda x: SessionDetector.detect(x.timestamp()))
        
        logger.info("  Extracting complex universal features...")
        df = UniversalFeatureStore.extract_features(df, symbol, "M15")
        if df.empty: continue
        
        logger.info("  Labeling universal outcomes (Virtual Execution)...")
        df = df.dropna(subset=['close', 'high', 'low', 'atr', 'adx'])
        df = df.reset_index(drop=True)
        
        outcomes_df = UniversalOutcomeStore.label_outcomes(df, sl_atr_mult=args.sl_mult, tp_atr_mult=args.tp_mult)
        if outcomes_df.empty: continue
            
        logger.info(f"  Saving {len(df)} features and {len(outcomes_df)} outcomes to Parquet Data Lake...")
        UniversalFeatureStore.save_partitioned(df, base_dir)
        UniversalOutcomeStore.save_partitioned(outcomes_df, base_dir)
        
        total_features_saved += len(df)
        total_outcomes_saved += len(outcomes_df)
        
        logger.info(f"  Joining simulated outcomes for Pattern Miner...")
        keep_cols = ['feature_uuid', 'symbol', 'entry_time_utc', 'year', 'month', 'session_label', 'regime', 
                     'atr_bucket', 'adx_bucket', 'trend_bucket']
        
        joined = outcomes_df.merge(df[keep_cols], on='feature_uuid', how='inner')
        # Rename symbols back to match the older logic just in case
        joined['symbol'] = joined['symbol_x']
        all_outcomes.append(joined)

    if not all_outcomes:
        logger.error("No outcomes generated.")
        return

    df_merged = pd.concat(all_outcomes, ignore_index=True)
    logger.info(f"Mining patterns across {len(df_merged)} total simulated pairs...")
    
    disc_json, blk_json, final_yaml, total_patterns_mined = PatternDatabase.mine_patterns(df_merged, base_dir, args.sl_mult, args.tp_mult)
    
    # Load ABC baseline
    track_a_stats = "No baseline data found."
    csv_path = os.path.join(base_dir, "results", "research_backtest_v2_trades.csv")
    if os.path.exists(csv_path):
        df_abc = pd.read_csv(csv_path)
        from research.pattern_database import PatternDatabase as PM
        df_abc['pnl_r'] = df_abc['r_multiple']
        track_a_stats = df_abc.groupby('engine').apply(PM.calc_metrics).round(2).to_markdown()

    # Track B Stats
    track_b_stats = "No patterns promoted."
    if disc_json:
        df_promoted = pd.DataFrame(disc_json)
        track_b_summary = df_promoted.groupby('promotion_status')[['occurrences', 'profit_factor', 'expectancy_r']].mean().round(2)
        track_b_stats = track_b_summary.to_markdown()

    report_content = f"""# Pattern Discovery Report
*Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*

## Data Lake Infrastructure
- **Universal Features Saved**: {total_features_saved}
- **Universal Outcomes Saved**: {total_outcomes_saved}
- **Patterns Mined**: {total_patterns_mined}
- **Storage Paths**:
  - Features: `data/feature_store/symbol=.../year=.../*.parquet`
  - Outcomes: `data/outcome_store/symbol=.../year=.../*.parquet`
  - Patterns: `data/pattern_store/pattern_database.parquet`

## Track A: Predefined Strategy Baseline (ABC Engine)
{track_a_stats}

## Track B: Pattern Discovery Intelligence
*Average performance of discovered edges.*
{track_b_stats}

## Top 10 VALIDATED Patterns
"""
    if disc_json:
        df_top = pd.DataFrame(disc_json)
        df_top = df_top[df_top['promotion_status'] == 'RESEARCH_VALIDATED'].sort_values('profit_factor', ascending=False).head(10)
        if not df_top.empty:
            report_content += df_top[['symbol', 'session_label', 'direction', 'regime', 'horizon', 'occurrences', 'profit_factor', 'expectancy_r']].round(2).to_markdown()
        else:
            report_content += "None."
    else:
        report_content += "None."

    report_content += "\n\n## Worst 10 REJECTED Patterns (Blacklist)\n"
    if blk_json:
        df_blk = pd.DataFrame(blk_json)
        df_blk = df_blk[df_blk['occurrences'] >= 50].sort_values('profit_factor', ascending=True).head(10)
        if not df_blk.empty:
            report_content += df_blk[['symbol', 'session_label', 'direction', 'regime', 'horizon', 'occurrences', 'profit_factor', 'expectancy_r']].round(2).to_markdown()
        else:
            report_content += "None."
    else:
        report_content += "None."

    report_path = os.path.join(base_dir, "reports", "PATTERN_DISCOVERY_REPORT.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(report_content)
    
    logger.info("Universal Pattern Discovery completed successfully.")

if __name__ == '__main__':
    main()
