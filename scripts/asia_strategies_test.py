import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator

def calculate_drawdown_pct(trades, initial_capital=10000.0):
    if not trades: return 0.0
    capital = initial_capital
    peak = capital
    max_dd_pct = 0.0
    for t in trades:
        capital += t['pnl']
        if capital > peak: peak = capital
        dd_pct = (peak - capital) / peak * 100
        if dd_pct > max_dd_pct: max_dd_pct = dd_pct
    return max_dd_pct

def calculate_sharpe(trades):
    if len(trades) < 2: return 0.0
    pnls = [t['pnl'] for t in trades]
    if np.std(pnls) == 0: return 0.0
    return (np.mean(pnls) / np.std(pnls)) * np.sqrt(252)

def print_results(name, trades):
    print(f"\n--- Strategy {name} ---")
    if not trades:
        print("No trades.")
        return
        
    wins = [t for t in trades if t['result'] == 'WIN']
    losses = [t for t in trades if t['result'] == 'LOSS']
    
    total_trades = len(trades)
    win_rate = len(wins) / total_trades * 100
    
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else 999.99
    
    max_dd_pct = calculate_drawdown_pct(trades)
    sharpe = calculate_sharpe(trades)
    
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Max DD: {max_dd_pct:.2f}%")
    print(f"Sharpe: {sharpe:.2f}")

def main():
    symbol = "XAUUSD"
    print("Connecting to MT5...")
    if not mt5_client.connect(): return
        
    print("Fetching 100,000 candles for XAUUSD...")
    df = mt5_client.get_historical_data(symbol, "M5", 100000)
    df = IndicatorCalculator.add_indicators(df)
    
    # Add EMA20 for Strategy C
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    records = df.to_dict('records')
    
    trades_A = []
    trades_B = []
    trades_C = []
    
    # State A
    a_high, a_low, a_mid = None, None, None
    a_in_trade, a_dir, a_entry, a_sl, a_tp = False, None, 0.0, 0.0, 0.0
    
    # State B
    b_high, b_low = None, None
    b_in_trade, b_dir, b_entry, b_sl, b_tp = False, None, 0.0, 0.0, 0.0
    
    # State C
    c_in_trade, c_dir, c_entry, c_sl, c_tp = False, None, 0.0, 0.0, 0.0
    
    for i in range(200, len(records) - 1):
        c = records[i]
        prev_c = records[i-1]
        h = c['hour']
        
        # --- Strategy A: Asian Range Fade ---
        # Build Range
        if 20 <= h <= 23:
            if h == 20 and prev_c['hour'] == 19:
                a_high, a_low = c['high'], c['low']
            else:
                if a_high is not None:
                    a_high = max(a_high, c['high'])
                    a_low = min(a_low, c['low'])
        if h == 0 and prev_c['hour'] == 23 and a_high is not None:
            a_mid = (a_high + a_low) / 2
            
        # Manage Trade A
        if a_in_trade:
            if a_dir == "BUY":
                if c['low'] <= a_sl: trades_A.append({"pnl": a_sl - a_entry, "result": "LOSS"}); a_in_trade = False
                elif c['high'] >= a_tp: trades_A.append({"pnl": a_tp - a_entry, "result": "WIN"}); a_in_trade = False
            else:
                if c['high'] >= a_sl: trades_A.append({"pnl": a_entry - a_sl, "result": "LOSS"}); a_in_trade = False
                elif c['low'] <= a_tp: trades_A.append({"pnl": a_entry - a_tp, "result": "WIN"}); a_in_trade = False
                
            if a_in_trade and h >= 7:
                pnl = c['close'] - a_entry if a_dir == "BUY" else a_entry - c['close']
                trades_A.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"}); a_in_trade = False
                
        # Enter Trade A (00:00 - 06:00 UTC)
        if not a_in_trade and 0 <= h < 6 and a_high is not None and a_mid is not None:
            if (a_high - a_low) >= 5:
                rsi, atr = c.get('rsi', 50), c.get('atr', 2.0)
                # SL 1.5 ATR to avoid noise stopping out 87% of trades
                if c['low'] < a_low and rsi < 35:
                    a_in_trade, a_dir, a_entry, a_tp, a_sl = True, "BUY", c['close'], a_mid, c['close'] - (1.5 * atr)
                elif c['high'] > a_high and rsi > 65:
                    a_in_trade, a_dir, a_entry, a_tp, a_sl = True, "SELL", c['close'], a_mid, c['close'] + (1.5 * atr)

        # --- Strategy B: London Breakout of Asia Range ---
        if 0 <= h <= 6:
            if h == 0 and prev_c['hour'] == 23:
                b_high, b_low = c['high'], c['low']
            else:
                if b_high is not None:
                    b_high = max(b_high, c['high'])
                    b_low = min(b_low, c['low'])
                    
        if b_in_trade:
            if b_dir == "BUY":
                if c['low'] <= b_sl: trades_B.append({"pnl": b_sl - b_entry, "result": "LOSS"}); b_in_trade = False
                elif c['high'] >= b_tp: trades_B.append({"pnl": b_tp - b_entry, "result": "WIN"}); b_in_trade = False
            else:
                if c['high'] >= b_sl: trades_B.append({"pnl": b_entry - b_sl, "result": "LOSS"}); b_in_trade = False
                elif c['low'] <= b_tp: trades_B.append({"pnl": b_entry - b_tp, "result": "WIN"}); b_in_trade = False
            if b_in_trade and h >= 18:
                pnl = c['close'] - b_entry if b_dir == "BUY" else b_entry - c['close']
                trades_B.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"}); b_in_trade = False
                
        # Enter Trade B (Exactly at 07:00 UTC)
        if not b_in_trade and h == 7 and b_high is not None:
            if c['close'] > b_high:
                b_in_trade, b_dir, b_entry, b_sl, b_tp = True, "BUY", c['close'], b_low, c['close'] + 1.5 * (b_high - b_low)
            elif c['close'] < b_low:
                b_in_trade, b_dir, b_entry, b_sl, b_tp = True, "SELL", c['close'], b_high, c['close'] - 1.5 * (b_high - b_low)

        # --- Strategy C: Tokyo RSI Exhaustion ---
        if c_in_trade:
            if c_dir == "BUY":
                if c['low'] <= c_sl: trades_C.append({"pnl": c_sl - c_entry, "result": "LOSS"}); c_in_trade = False
                elif c['high'] >= c_tp: trades_C.append({"pnl": c_tp - c_entry, "result": "WIN"}); c_in_trade = False
            else:
                if c['high'] >= c_sl: trades_C.append({"pnl": c_entry - c_sl, "result": "LOSS"}); c_in_trade = False
                elif c['low'] <= c_tp: trades_C.append({"pnl": c_entry - c_tp, "result": "WIN"}); c_in_trade = False
            if c_in_trade and h >= 6:
                pnl = c['close'] - c_entry if c_dir == "BUY" else c_entry - c['close']
                trades_C.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"}); c_in_trade = False
                
        # Enter Trade C (00:00 - 04:00 UTC)
        if not c_in_trade and 0 <= h < 4:
            adx, rsi, atr, ema20 = c.get('adx', 0), c.get('rsi', 50), c.get('atr', 2.0), c.get('ema20', c['close'])
            if adx < 20:
                if rsi < 30 and c['close'] > ema20:
                    c_in_trade, c_dir, c_entry, c_sl, c_tp = True, "BUY", c['close'], c['close'] - atr, c['close'] + atr
                elif rsi > 70 and c['close'] < ema20:
                    c_in_trade, c_dir, c_entry, c_sl, c_tp = True, "SELL", c['close'], c['close'] + atr, c['close'] - atr

    print_results("A: Asian Range Fade (1.5 ATR SL)", trades_A)
    print_results("B: London Breakout of Asia Range", trades_B)
    print_results("C: Tokyo RSI Exhaustion", trades_C)

if __name__ == '__main__': main()
