import os
import sys
import pandas as pd
import numpy as np

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
    
    # Pre-calculate body and rolling body mean
    df['body'] = abs(df['close'] - df['open'])
    df['body_mean_10'] = df['body'].rolling(10).mean()
    
    records = df.to_dict('records')
    
    trades_C0 = [] # Base (Price Action Reversal)
    trades_C1 = [] # + Volume Spike
    
    state_C0 = {'in': False, 'dir': None, 'entry': 0, 'sl': 0, 'tp': 0}
    state_C1 = {'in': False, 'dir': None, 'entry': 0, 'sl': 0, 'tp': 0}
    
    for i in range(200, len(records) - 1):
        c = records[i]
        prev_c = records[i-1]
        h = c['hour']
            
        def manage_trade(state, trades_list):
            if state['in']:
                if state['dir'] == "BUY":
                    if c['low'] <= state['sl']: trades_list.append({"pnl": state['sl'] - state['entry'], "result": "LOSS"}); state['in'] = False
                    elif c['high'] >= state['tp']: trades_list.append({"pnl": state['tp'] - state['entry'], "result": "WIN"}); state['in'] = False
                else:
                    if c['high'] >= state['sl']: trades_list.append({"pnl": state['entry'] - state['sl'], "result": "LOSS"}); state['in'] = False
                    elif c['low'] <= state['tp']: trades_list.append({"pnl": state['entry'] - state['tp'], "result": "WIN"}); state['in'] = False
                    
                if state['in'] and h >= 6:
                    pnl = c['close'] - state['entry'] if state['dir'] == "BUY" else state['entry'] - c['close']
                    trades_list.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"})
                    state['in'] = False

        manage_trade(state_C0, trades_C0)
        manage_trade(state_C1, trades_C1)
                
        # Trade Window: 00:00 - 04:00 UTC
        if 0 <= h < 4:
            rsi = c.get('rsi', 50)
            adx = c.get('adx', 50)
            atr = c.get('atr', 2.0)
            
            bullish_candle = c['close'] > c['open']
            bearish_candle = c['close'] < c['open']
            prev_bearish = prev_c['close'] < prev_c['open']
            prev_bullish = prev_c['close'] > prev_c['open']
            
            body_mean = c.get('body_mean_10', 0.1)
            volume_spike = c['body'] > (body_mean * 1.5) if body_mean > 0 else False
            
            if adx < 20:
                # BUY Setup
                if rsi < 30 and bullish_candle and prev_bearish:
                    if not state_C0['in']:
                        state_C0.update({'in': True, 'dir': 'BUY', 'entry': c['close'], 'sl': c['close'] - atr, 'tp': c['close'] + atr})
                    if not state_C1['in'] and volume_spike:
                        state_C1.update({'in': True, 'dir': 'BUY', 'entry': c['close'], 'sl': c['close'] - atr, 'tp': c['close'] + atr})
                        
                # SELL Setup
                if rsi > 70 and bearish_candle and prev_bullish:
                    if not state_C0['in']:
                        state_C0.update({'in': True, 'dir': 'SELL', 'entry': c['close'], 'sl': c['close'] + atr, 'tp': c['close'] - atr})
                    if not state_C1['in'] and volume_spike:
                        state_C1.update({'in': True, 'dir': 'SELL', 'entry': c['close'], 'sl': c['close'] + atr, 'tp': c['close'] - atr})

    print_results("Strategy C0 (Price Action Reversal)", trades_C0)
    print_results("Strategy C1 (+ Volume/Body Spike)", trades_C1)

if __name__ == '__main__': main()
