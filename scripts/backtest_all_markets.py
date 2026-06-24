import os
import sys
import glob
import yaml
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from xgboost import XGBClassifier

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml.dataset_builder import build_dataset

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("MultiMarketBacktest")

FEATURES = [
    "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
    "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc", "is_high_volatility", "is_buy",
    "recent_high_20_distance", "recent_low_20_distance"
]
TARGET = "label"

def load_symbols():
    try:
        with open("config/symbols.yaml", "r") as f:
            return yaml.safe_load(f).get("symbols", {})
    except Exception as e:
        logger.error(f"Failed to load symbols.yaml: {e}")
        return {}

def get_latest_dataset(symbol):
    files = glob.glob(f"datasets/{symbol}/{symbol}_dataset_atr_*.csv")
    if not files:
        return None
    # Sort to get the latest version
    files.sort(reverse=True)
    return files[0]

def simulate_pnl(y_true, y_pred):
    trades = (y_pred == 1)
    if trades.sum() == 0:
        return 0, 0.0, 0.0, 0.0, 0.0
        
    wins = (y_true == 1) & trades
    losses = (y_true == 0) & trades
    
    n_trades = trades.sum()
    n_wins = wins.sum()
    n_losses = losses.sum()
    
    win_rate = n_wins / n_trades
    total_r = (n_wins * 2.0) + (n_losses * -1.0)
    expectancy_r = total_r / n_trades
    
    pnl_seq = np.where(y_true[trades] == 1, 2.0, -1.0)
    cum_r = np.cumsum(pnl_seq)
    peak_r = np.maximum.accumulate(cum_r)
    dd_r = peak_r - cum_r
    max_dd_r = dd_r.max() if len(dd_r) > 0 else 0.0
    
    return n_trades, win_rate, expectancy_r, total_r, max_dd_r

def evaluate_thresholds(y_true, probs):
    thresholds = [0.35, 0.40, 0.45, 0.50, 0.55]
    best_expectancy = -999.0
    best_stats = None
    
    for th in thresholds:
        y_pred = (probs >= th).astype(int)
        n_trades, win_rate, exp_r, total_r, max_dd = simulate_pnl(y_true, y_pred)
        
        # We need at least some trades to consider it valid
        if n_trades > 10 and exp_r > best_expectancy:
            best_expectancy = exp_r
            best_stats = {
                "Threshold": th,
                "Trades": n_trades,
                "Win Rate": f"{win_rate:.1%}",
                "Expectancy (R)": round(exp_r, 2),
                "Total Profit (R)": round(total_r, 2),
                "Max DD (R)": round(max_dd, 2)
            }
            
    if not best_stats:
        return {
            "Threshold": "N/A", "Trades": 0, "Win Rate": "0.0%",
            "Expectancy (R)": 0.0, "Total Profit (R)": 0.0, "Max DD (R)": 0.0
        }
    return best_stats

def main():
    print("=" * 70)
    print(" MULTI-MARKET BACKTEST ENGINE ")
    print("=" * 70)
    
    symbols_config = load_symbols()
    results = []
    
    for symbol, cfg in symbols_config.items():
        if not cfg.get("enabled", False):
            continue
            
        print(f"\nProcessing {symbol} ({cfg.get('display_name')})...")
        
        dataset_file = get_latest_dataset(symbol)
        if not dataset_file:
            print(f"Dataset not found for {symbol}. Building...")
            # We assume a default ATR of 2.0 for general datasets
            build_dataset(symbol, cfg.get("primary_timeframe", "M5"), 2.0)
            dataset_file = get_latest_dataset(symbol)
            
        if not dataset_file:
            print(f"Skipping {symbol}: Could not generate dataset.")
            continue
            
        print(f"Loading {dataset_file}...")
        df = pd.read_csv(dataset_file)
        
        # Verify columns exist
        missing_cols = [c for c in FEATURES + [TARGET] if c not in df.columns]
        if missing_cols:
            print(f"Skipping {symbol}: Missing columns {missing_cols}")
            continue
            
        # Clean data
        df = df.dropna(subset=FEATURES + [TARGET])
        
        # Chronological Split (80% Train, 20% Test)
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]
        
        if len(train_df) < 100 or len(test_df) < 50:
            print(f"Skipping {symbol}: Not enough data points.")
            continue
            
        X_train, y_train = train_df[FEATURES], train_df[TARGET]
        X_test, y_test = test_df[FEATURES], test_df[TARGET]
        
        print(f"Training XGBoost for {symbol} (Train: {len(X_train)}, Test: {len(X_test)})...")
        model = XGBClassifier(
            n_estimators=300,
            learning_rate=0.01,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss'
        )
        model.fit(X_train, y_train)
        
        probs = model.predict_proba(X_test)[:, 1]
        
        stats = evaluate_thresholds(y_test.values, probs)
        stats["Symbol"] = symbol
        stats["Asset Class"] = cfg.get("asset_class", "UNKNOWN")
        results.append(stats)
        
    print("\n" + "=" * 80)
    print(" MULTI-MARKET BACKTEST RESULTS ")
    print("=" * 80)
    
    if not results:
        print("No valid results generated.")
        return
        
    df_results = pd.DataFrame(results)
    # Reorder columns
    cols = ["Symbol", "Asset Class", "Threshold", "Trades", "Win Rate", "Expectancy (R)", "Total Profit (R)", "Max DD (R)"]
    df_results = df_results[cols]
    
    # Print formatted table
    print(df_results.to_string(index=False))
    
    os.makedirs("reports", exist_ok=True)
    report_file = f"reports/multi_market_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df_results.to_csv(report_file, index=False)
    print(f"\nResults exported to {report_file}")

if __name__ == "__main__":
    main()
