import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import os
import itertools
import json
from config.settings import settings
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from backtest.runner import BacktestRunner

def run_optimizer():
    reports_dir = "backtest/reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    if not mt5_client.connect():
        print("Failed to connect to MT5.")
        return

    print("Fetching 50,000 candles...")
    df = mt5_client.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, 50000)
    if df is None or df.empty:
        print("No data fetched.")
        return

    print("Calculating indicators (vectorized)...")
    df = IndicatorCalculator.add_indicators(df)

    from market.regime_detector import RegimeDetector
    from strategy.market_score import MarketScoreCalculator

    print("Pre-calculating setups for all candles (this takes a few seconds)...")
    scores_list = []
    for i in range(200, len(df)):
        df_slice = df.iloc[i-5:i+1]
        regime = RegimeDetector.detect(df_slice)
        # Use SetupEvaluator directly
        from strategy.setups import SetupEvaluator
        setups = SetupEvaluator.evaluate_all(df_slice, regime)
        scores_list.append({"setups": setups, "regime": regime})

    # Parameter Space
    atr_multipliers = [1.0, 1.5, 2.0, 2.5]
    rr_ratios = [1.0, 1.5, 2.0, 2.5]
    thresholds = [60, 70, 80, 85, 90]
    
    setup_names = [
        "London Breakout", 
        "NY Breakout", 
        "EMA Pullback Continuation", 
        "RSI Exhaustion Reversal", 
        "Range Boundary Bounce", 
        "Volatility Expansion Breakout"
    ]
    
    combinations = list(itertools.product(atr_multipliers, rr_ratios, thresholds))
    total_combs = len(combinations)
    
    runner = BacktestRunner(spread_points=settings.BACKTEST_SPREAD_POINTS)
    records = df.to_dict('records')
    
    setup_summaries = []

    for setup_name in setup_names:
        print(f"\n--- Optimizing Setup: {setup_name} ---")
        best_pf = -1
        best_result = None
        
        for idx, (atr_mult, rr, th) in enumerate(combinations):
            trades = runner.run(records, scores_list, th, atr_mult, rr, target_setup=setup_name)
            
            trades_df = pd.DataFrame(trades)
            if not trades_df.empty:
                total_trades = len(trades_df)
                wins = len(trades_df[trades_df['result_r'] > 0])
                win_rate = wins / total_trades
                
                avg_r = trades_df['result_r'].mean()
                std_r = trades_df['result_r'].std()
                sharpe = (avg_r / std_r) if std_r and std_r > 0 else 0
                
                trades_df['cumulative_r'] = trades_df['result_r'].cumsum()
                trades_df['peak'] = trades_df['cumulative_r'].cummax()
                trades_df['drawdown'] = trades_df['peak'] - trades_df['cumulative_r']
                max_dd_r = trades_df['drawdown'].max()
                
                gross_profit = trades_df[trades_df['result_r'] > 0]['result_r'].sum()
                gross_loss = abs(trades_df[trades_df['result_r'] < 0]['result_r'].sum())
                pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                res = {
                    "setup_name": setup_name,
                    "best_threshold": th,
                    "best_atr_multiplier": atr_mult,
                    "best_rr": rr,
                    "total_trades": total_trades,
                    "win_rate": round(win_rate * 100, 2),
                    "profit_factor": round(pf, 3),
                    "expectancy": round(avg_r, 3),
                    "max_drawdown_r": round(max_dd_r, 2),
                    "sharpe": round(sharpe, 3)
                }
                
                # Keep track of best result for this setup based on PF
                if pf > best_pf:
                    best_pf = pf
                    best_result = res
                    
        if best_result:
            setup_summaries.append(best_result)
        else:
            setup_summaries.append({
                "setup_name": setup_name,
                "best_threshold": 0,
                "best_atr_multiplier": 0,
                "best_rr": 0,
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "max_drawdown_r": 0.0,
                "sharpe": 0.0
            })
            
    summary_df = pd.DataFrame(setup_summaries)
    
    today = datetime.now().strftime("%Y-%m-%d")
    summary_df.to_csv(f"{reports_dir}/setup_summary_{today}.csv", index=False)
    
    print("\nSetup Summary Top 6:")
    print(summary_df.sort_values(by='profit_factor', ascending=False).to_string(index=False))

if __name__ == "__main__":
    run_optimizer()
