import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import os
from config.settings import settings
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from backtest.runner import BacktestRunner

def run_calibration():
    # Setup directories
    reports_dir = "backtest/reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    # Init MT5
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

    print("Pre-calculating scores for all candles (this takes a few seconds)...")
    scores_list = []
    for i in range(200, len(df)):
        df_slice = df.iloc[i-5:i+1]
        regime = RegimeDetector.detect(df_slice)
        market_score = MarketScoreCalculator.calculate(df_slice, regime)
        scores_list.append({"market_score": market_score, "regime": regime})

    thresholds = [60, 65, 70, 75, 80, 85, 90]
    
    results = []
    
    runner = BacktestRunner(
        spread_points=settings.BACKTEST_SPREAD_POINTS,
        sl_points=500.0,
        rr_ratio=2.0
    )

    for th in thresholds:
        print(f"--- Simulating Threshold: {th} ---")
        trades = runner.run(df, scores_list, th)
        
        trades_df = pd.DataFrame(trades)
        if not trades_df.empty:
            trades_df.to_csv(f"{reports_dir}/trades_threshold_{th}.csv", index=False)
            
            total_trades = len(trades_df)
            wins = len(trades_df[trades_df['result_r'] > 0])
            win_rate = wins / total_trades * 100
            
            avg_r = trades_df['result_r'].mean()
            
            # Drawdown and equity curve
            trades_df['cumulative_r'] = trades_df['result_r'].cumsum()
            trades_df['peak'] = trades_df['cumulative_r'].cummax()
            trades_df['drawdown'] = trades_df['peak'] - trades_df['cumulative_r']
            max_dd = trades_df['drawdown'].max()
            
            # Profit Factor
            gross_profit = trades_df[trades_df['result_r'] > 0]['result_r'].sum()
            gross_loss = abs(trades_df[trades_df['result_r'] < 0]['result_r'].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Cons losses
            consec_losses = 0
            max_consec_losses = 0
            for r in trades_df['result_r']:
                if r < 0:
                    consec_losses += 1
                    max_consec_losses = max(max_consec_losses, consec_losses)
                else:
                    consec_losses = 0
                    
            buy_count = len(trades_df[trades_df['direction'] == 'BUY'])
            sell_count = len(trades_df[trades_df['direction'] == 'SELL'])
            
            results.append({
                "Threshold": th,
                "Total Trades": total_trades,
                "Win Rate (%)": round(win_rate, 2),
                "Average R": round(avg_r, 2),
                "Max Drawdown (R)": round(max_dd, 2),
                "Profit Factor": round(pf, 2),
                "Max Consecutive Losses": max_consec_losses,
                "Buy Count": buy_count,
                "Sell Count": sell_count
            })
        else:
            results.append({
                "Threshold": th,
                "Total Trades": 0,
                "Win Rate (%)": 0,
                "Average R": 0,
                "Max Drawdown (R)": 0,
                "Profit Factor": 0,
                "Max Consecutive Losses": 0,
                "Buy Count": 0,
                "Sell Count": 0
            })

    results_df = pd.DataFrame(results)
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = f"{reports_dir}/score_calibration_{today}.csv"
    results_df.to_csv(report_path, index=False)
    
    print("\nCalibration Results:")
    print(results_df.to_string(index=False))
    
if __name__ == "__main__":
    run_calibration()
