"""analytics/shadow_analyzer.py — Analyze shadow trades to determine GO LIVE readiness."""
import sys
import os
import argparse
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Add root directory to path to allow imports when run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.repository import repository

# ASSUMPTION: 
# The model for shadow trades exists (e.g., ShadowTrade) or the table 'shadow_trades' exists.
# We will use pandas.read_sql directly to handle the analytical queries cleanly.

logger = logging.getLogger("ShadowAnalyzer")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def analyze_shadow_trades(days: int = 30):
    print("=" * 60)
    print(f" SHADOW MODE ANALYSIS ({days} DAYS) ")
    print("=" * 60)

    try:
        engine = repository.engine
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Note: Assuming table name is 'shadow_trades' and has columns:
        # id, signal_id, symbol, direction, volume, entry_price, sl_points, tp_points,
        # simulated_exit_price, simulated_pnl_r, is_win, created_at, closed_at
        query = f"SELECT * FROM shadow_trades WHERE created_at >= '{cutoff_date.isoformat()}'"
        
        try:
            df = pd.read_sql(query, engine)
        except Exception as db_err:
            print(f"Database query failed. Ensure 'shadow_trades' table exists. Error: {db_err}")
            return
            
        if df.empty:
            print("No shadow trades found in the specified period.")
            print("🟡 VERDICT: CONTINUE SHADOW — 5 thresholds not met, need more data")
            return

        # Ensure datetime
        df['created_at'] = pd.to_datetime(df['created_at'])
        
        # 1. n_trades
        n_trades = len(df)
        
        # 2. win_rate
        wins = df[df['is_win'] == True]
        losses = df[df['is_win'] == False]
        win_rate = len(wins) / n_trades if n_trades > 0 else 0.0
        
        # 3. avg_win_r
        avg_win_r = wins['simulated_pnl_r'].mean() if not wins.empty else 0.0
        
        # 4. avg_loss_r
        avg_loss_r = losses['simulated_pnl_r'].mean() if not losses.empty else 0.0
        
        # 5. expectancy
        expectancy = (win_rate * avg_win_r) + ((1 - win_rate) * avg_loss_r)
        
        # 6. profit_factor
        sum_wins_r = wins['simulated_pnl_r'].sum()
        sum_losses_r = abs(losses['simulated_pnl_r'].sum())
        profit_factor = (sum_wins_r / sum_losses_r) if sum_losses_r > 0 else float('inf')
        
        # 7. max_drawdown_r
        df = df.sort_values('created_at')
        df['cum_r'] = df['simulated_pnl_r'].cumsum()
        df['peak_r'] = df['cum_r'].cummax()
        df['drawdown_r'] = df['peak_r'] - df['cum_r']
        max_drawdown_r = df['drawdown_r'].max() if not df.empty else 0.0
        
        # 8. sharpe_r
        df['date'] = df['created_at'].dt.date
        daily_r = df.groupby('date')['simulated_pnl_r'].sum()
        mean_daily_r = daily_r.mean()
        std_daily_r = daily_r.std()
        sharpe_r = (mean_daily_r / std_daily_r * np.sqrt(252)) if std_daily_r > 0 else 0.0
        
        # 9. avg_trade_per_day
        days_elapsed = (df['created_at'].max() - df['created_at'].min()).days
        days_elapsed = max(1, days_elapsed)
        avg_trade_per_day = n_trades / days_elapsed

        # Print Metrics
        print(f"1. Total Trades:       {n_trades}")
        print(f"2. Win Rate:           {win_rate:.2%}")
        print(f"3. Avg Win (R):        {avg_win_r:.2f}R")
        print(f"4. Avg Loss (R):       {avg_loss_r:.2f}R")
        print(f"5. Expectancy:         {expectancy:.2f}R per trade")
        print(f"6. Profit Factor:      {profit_factor:.2f}")
        print(f"7. Max Drawdown (R):   {max_drawdown_r:.2f}R")
        print(f"8. Sharpe Ratio (R):   {sharpe_r:.2f}")
        print(f"9. Trades / Day:       {avg_trade_per_day:.1f}")
        print("\n10. SLIPPAGE NOTE:")
        print("    Shadow mode executes exactly at signal price with zero slippage.")
        print("    Real live trading will have slippage and spread, reducing actual R.")
        print("-" * 60)

        # Evaluate Thresholds
        print(" THRESHOLD EVALUATION ")
        print("-" * 60)
        
        evaluations = [
            ("Win Rate >= 45%", win_rate >= 0.45),
            ("Expectancy >= 0.20R", expectancy >= 0.20),
            ("Profit Factor >= 1.3", profit_factor >= 1.3),
            ("Max Drawdown <= 8.0R", max_drawdown_r <= 8.0),
            ("Sample Size >= 30", n_trades >= 30)
        ]
        
        fails = 0
        for name, passed in evaluations:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} | {name}")
            if not passed:
                fails += 1
                
        print("=" * 60)
        
        # Verdict
        if fails == 0:
            print("🟢 VERDICT: GO LIVE — metrics meet minimum thresholds")
        elif fails <= 2:
            print(f"🟡 VERDICT: CONTINUE SHADOW — {fails} thresholds not met, need more data")
        else:
            print(f"🔴 VERDICT: ABORT — strategy edge not proven, do NOT go live")

    except Exception as e:
        logger.error(f"Error analyzing shadow trades: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Shadow Trades.")
    parser.add_argument("--days", type=int, default=30, help="Days of history to analyze")
    args = parser.parse_args()
    
    analyze_shadow_trades(days=args.days)
