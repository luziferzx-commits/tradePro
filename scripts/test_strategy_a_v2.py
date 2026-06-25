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
    print(f"\n--- {name} ---")
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
    
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Max DD: {calculate_drawdown_pct(trades):.2f}%")
    print(f"Sharpe: {calculate_sharpe(trades):.2f}")

def main():
    symbol = "XAUUSD"
    if not mt5_client.connect(): return
        
    df = mt5_client.get_historical_data(symbol, "M5", 100000)
    df = IndicatorCalculator.add_indicators(df)
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    
    # Pre-calculate rolling variables for divergence
    df['close_shift_3'] = df['close'].shift(3)
    df['rsi_shift_3'] = df['rsi'].shift(3)
    
    records = df.to_dict('records')
    
    trades_A0 = [] # Base
    trades_A1 = [] # + Wick + Extension
    trades_A2 = [] # + Divergence
    
    state_A0 = {'in': False, 'dir': None, 'entry': 0, 'sl': 0, 'tp': 0}
    state_A1 = {'in': False, 'dir': None, 'entry': 0, 'sl': 0, 'tp': 0}
    state_A2 = {'in': False, 'dir': None, 'entry': 0, 'sl': 0, 'tp': 0}
    
    a_high, a_low, a_mid = None, None, None
    
    for i in range(200, len(records) - 1):
        c = records[i]
        prev_c = records[i-1]
        h = c['hour']
        
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
            
        # Manage Trades function
        def manage_trade(state, trades_list):
            if state['in']:
                if state['dir'] == "BUY":
                    if c['low'] <= state['sl']: trades_list.append({"pnl": state['sl'] - state['entry'], "result": "LOSS"}); state['in'] = False
                    elif c['high'] >= state['tp']: trades_list.append({"pnl": state['tp'] - state['entry'], "result": "WIN"}); state['in'] = False
                else:
                    if c['high'] >= state['sl']: trades_list.append({"pnl": state['entry'] - state['sl'], "result": "LOSS"}); state['in'] = False
                    elif c['low'] <= state['tp']: trades_list.append({"pnl": state['entry'] - state['tp'], "result": "WIN"}); state['in'] = False
                    
                if state['in'] and h >= 7:
                    pnl = c['close'] - state['entry'] if state['dir'] == "BUY" else state['entry'] - c['close']
                    trades_list.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"})
                    state['in'] = False

        manage_trade(state_A0, trades_A0)
        manage_trade(state_A1, trades_A1)
        manage_trade(state_A2, trades_A2)
                
        # Entry Logic (00:00 - 06:00 UTC)
        if 0 <= h < 6 and a_high is not None and a_mid is not None and (a_high - a_low) >= 5:
            atr = c.get('atr', 2.0)
            rsi = c.get('rsi', 50)
            body = abs(c['close'] - c['open'])
            upper_wick = c['high'] - max(c['close'], c['open'])
            lower_wick = min(c['close'], c['open']) - c['low']
            
            # SELL Setups (Price > Range High)
            if c['high'] > a_high:
                ext = (c['close'] - a_high) / atr
                has_ext = ext >= 0.3
                has_wick = upper_wick >= body * 0.3
                
                # Divergence: Price higher but RSI lower
                price_higher = c['close'] > c['close_shift_3']
                rsi_lower = rsi < c['rsi_shift_3']
                has_div = price_higher and rsi_lower
                
                # A0: Base (Only RSI > 65)
                if not state_A0['in'] and rsi > 65:
                    state_A0.update({'in': True, 'dir': 'SELL', 'entry': c['close'], 'sl': c['close'] + 1.5*atr, 'tp': a_mid})
                
                # A1: + Extension + Wick
                if not state_A1['in'] and rsi > 65 and has_ext and has_wick:
                    state_A1.update({'in': True, 'dir': 'SELL', 'entry': c['close'], 'sl': c['close'] + 1.5*atr, 'tp': a_mid})
                    
                # A2: A1 + Divergence
                if not state_A2['in'] and rsi > 65 and has_ext and has_wick and has_div:
                    state_A2.update({'in': True, 'dir': 'SELL', 'entry': c['close'], 'sl': c['close'] + 1.5*atr, 'tp': a_mid})
                    
            # BUY Setups (Price < Range Low)
            elif c['low'] < a_low:
                ext = (a_low - c['close']) / atr
                has_ext = ext >= 0.3
                has_wick = lower_wick >= body * 0.3
                
                # Divergence: Price lower but RSI higher
                price_lower = c['close'] < c['close_shift_3']
                rsi_higher = rsi > c['rsi_shift_3']
                has_div = price_lower and rsi_higher
                
                # A0: Base (Only RSI < 35)
                if not state_A0['in'] and rsi < 35:
                    state_A0.update({'in': True, 'dir': 'BUY', 'entry': c['close'], 'sl': c['close'] - 1.5*atr, 'tp': a_mid})
                
                # A1: + Extension + Wick
                if not state_A1['in'] and rsi < 35 and has_ext and has_wick:
                    state_A1.update({'in': True, 'dir': 'BUY', 'entry': c['close'], 'sl': c['close'] - 1.5*atr, 'tp': a_mid})
                    
                # A2: A1 + Divergence
                if not state_A2['in'] and rsi < 35 and has_ext and has_wick and has_div:
                    state_A2.update({'in': True, 'dir': 'BUY', 'entry': c['close'], 'sl': c['close'] - 1.5*atr, 'tp': a_mid})

    print_results("Strategy A0 (Base)", trades_A0)
    print_results("Strategy A1 (+ Wick + Extension)", trades_A1)
    print_results("Strategy A2 (+ RSI Divergence)", trades_A2)

if __name__ == '__main__': main()
