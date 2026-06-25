import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from market.regime_detector import RegimeDetector
from strategy.market_score import MarketScoreCalculator

def main():
    symbol = "XAUUSD"
    timeframe = "M5"
    target_setup = "Asia Continuation"
    atr_multiplier = 15.0
    rr_ratio = 1.5
    
    print(f"Connecting to MT5...")
    if not mt5_client.connect():
        print("Failed to connect.")
        return
        
    print(f"Fetching 50,000 candles for {symbol}...") # Reduced to 50k for speed
    df = mt5_client.get_historical_data(symbol, timeframe, 50000)
    if df is None or df.empty:
        print("No data fetched.")
        return
        
    print("Calculating indicators...")
    df = IndicatorCalculator.add_indicators(df)
    
    print("Running backtest simulation...")
    records = df.to_dict('records')
    
    trades = []
    
    for i in range(100, len(records) - 100):
        df_slice = df.iloc[i-50:i+1]
        regime = RegimeDetector.detect(df_slice)
        
        # We only need the latest 5 candles for MarketScoreCalculator
        short_slice = df.iloc[i-5:i+1]
        
        score_result = MarketScoreCalculator.calculate(short_slice, regime, h4_trend="NEUTRAL", asset_class="FOREX")
        
        # We only care about Asia Continuation for this backtest
        if score_result['setup_name'] != target_setup or score_result['final_direction'] == "NEUTRAL":
            continue
            
        direction = score_result['final_direction']
        entry_candle = records[i]
        
        # Simple execution model: enter at close
        entry_price = entry_candle['close']
        atr = entry_candle['atr']
        
        sl_dist = atr * atr_multiplier
        tp_dist = sl_dist * rr_ratio
        
        if direction == "BUY":
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
        else:
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist
            
        # Forward simulation
        trade_result = None
        pnl = 0.0
        exit_time = None
        
        for j in range(i+1, len(records)):
            f_candle = records[j]
            high = f_candle['high']
            low = f_candle['low']
            
            if direction == "BUY":
                if low <= sl:
                    trade_result = "LOSS"
                    pnl = -sl_dist
                    exit_time = f_candle['time']
                    break
                elif high >= tp:
                    trade_result = "WIN"
                    pnl = tp_dist
                    exit_time = f_candle['time']
                    break
            else:
                if high >= sl:
                    trade_result = "LOSS"
                    pnl = -sl_dist
                    exit_time = f_candle['time']
                    break
                elif low <= tp:
                    trade_result = "WIN"
                    pnl = tp_dist
                    exit_time = f_candle['time']
                    break
                    
        if trade_result:
            trades.append({
                "entry_time": entry_candle['time'],
                "exit_time": exit_time,
                "direction": direction,
                "entry_price": entry_price,
                "pnl": pnl,
                "result": trade_result
            })
            
    print("\n--- Backtest Results ---")
    if not trades:
        print("No trades found.")
        return
        
    wins = [t for t in trades if t['result'] == 'WIN']
    losses = [t for t in trades if t['result'] == 'LOSS']
    
    total_trades = len(trades)
    win_rate = len(wins) / total_trades * 100
    
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else 999.99
    
    peak = 0
    max_dd = 0
    cumulative = 0
    for t in trades:
        cumulative += t['pnl']
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
            
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Max Drawdown: {max_dd:.2f} points")
    print(f"Net PnL (points): {gross_profit - gross_loss:.2f}")
    print(f"Period: {trades[0]['entry_time']} to {trades[-1]['entry_time']}")

if __name__ == '__main__':
    main()
