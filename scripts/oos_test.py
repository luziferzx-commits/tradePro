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
    max_dd_pct = calculate_drawdown_pct(trades)
    sharpe = calculate_sharpe(trades)
    
    avg_win = gross_profit / len(wins) if wins else 0
    avg_loss = gross_loss / len(losses) if losses else 0
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Avg Win: {avg_win:.2f} | Avg Loss: {avg_loss:.2f} | RR: {rr_ratio:.2f}")
    print(f"Max DD: {max_dd_pct:.2f}%")
    print(f"Sharpe: {sharpe:.2f}")

def main():
    symbol = "XAUUSD"
    if not mt5_client.connect(): return
        
    df = mt5_client.get_historical_data(symbol, "M5", 100000)
    df = IndicatorCalculator.add_indicators(df)
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    
    df['close_shift_3'] = df['close'].shift(3)
    df['rsi_shift_3'] = df['rsi'].shift(3)
    
    records = df.to_dict('records')
    
    # Split Out-Of-Sample (last 30,000 candles ~ 3.5 months)
    # We start from index len(records)-30000 to the end
    oos_start_idx = len(records) - 30000
    
    trades_A2_OOS = []
    trades_B_OOS = []
    
    state_A2 = {'in': False, 'dir': None, 'entry': 0, 'sl': 0, 'tp': 0}
    a_high, a_low, a_mid = None, None, None
    
    state_B = {'in': False, 'dir': None, 'entry': 0, 'sl': 0, 'tp': 0}
    b_high, b_low = None, None
    
    for i in range(oos_start_idx, len(records) - 1):
        c = records[i]
        prev_c = records[i-1]
        h = c['hour']
        
        # --- Strategy A2 ---
        if 20 <= h <= 23:
            if h == 20 and prev_c['hour'] == 19:
                a_high, a_low = c['high'], c['low']
            else:
                if a_high is not None:
                    a_high = max(a_high, c['high'])
                    a_low = min(a_low, c['low'])
        if h == 0 and prev_c['hour'] == 23 and a_high is not None:
            a_mid = (a_high + a_low) / 2
            
        if state_A2['in']:
            if state_A2['dir'] == "BUY":
                if c['low'] <= state_A2['sl']: trades_A2_OOS.append({"pnl": state_A2['sl'] - state_A2['entry'], "result": "LOSS"}); state_A2['in'] = False
                elif c['high'] >= state_A2['tp']: trades_A2_OOS.append({"pnl": state_A2['tp'] - state_A2['entry'], "result": "WIN"}); state_A2['in'] = False
            else:
                if c['high'] >= state_A2['sl']: trades_A2_OOS.append({"pnl": state_A2['entry'] - state_A2['sl'], "result": "LOSS"}); state_A2['in'] = False
                elif c['low'] <= state_A2['tp']: trades_A2_OOS.append({"pnl": state_A2['entry'] - state_A2['tp'], "result": "WIN"}); state_A2['in'] = False
            if state_A2['in'] and h >= 7:
                pnl = c['close'] - state_A2['entry'] if state_A2['dir'] == "BUY" else state_A2['entry'] - c['close']
                trades_A2_OOS.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"}); state_A2['in'] = False
                
        if not state_A2['in'] and 0 <= h < 6 and a_high is not None and a_mid is not None and (a_high - a_low) >= 5:
            atr, rsi = c.get('atr', 2.0), c.get('rsi', 50)
            body = abs(c['close'] - c['open'])
            upper_wick = c['high'] - max(c['close'], c['open'])
            lower_wick = min(c['close'], c['open']) - c['low']
            
            if c['high'] > a_high:
                if ((c['close'] - a_high) / atr) >= 0.3 and upper_wick >= body * 0.3 and c['close'] > c['close_shift_3'] and rsi < c['rsi_shift_3']:
                    if rsi > 65:
                        state_A2.update({'in': True, 'dir': 'SELL', 'entry': c['close'], 'sl': c['close'] + 1.5*atr, 'tp': a_mid})
            elif c['low'] < a_low:
                if ((a_low - c['close']) / atr) >= 0.3 and lower_wick >= body * 0.3 and c['close'] < c['close_shift_3'] and rsi > c['rsi_shift_3']:
                    if rsi < 35:
                        state_A2.update({'in': True, 'dir': 'BUY', 'entry': c['close'], 'sl': c['close'] - 1.5*atr, 'tp': a_mid})

        # --- Strategy B ---
        if 0 <= h <= 6:
            if h == 0 and prev_c['hour'] == 23:
                b_high, b_low = c['high'], c['low']
            else:
                if b_high is not None:
                    b_high = max(b_high, c['high'])
                    b_low = min(b_low, c['low'])
                    
        if state_B['in']:
            if state_B['dir'] == "BUY":
                if c['low'] <= state_B['sl']: trades_B_OOS.append({"pnl": state_B['sl'] - state_B['entry'], "result": "LOSS"}); state_B['in'] = False
                elif c['high'] >= state_B['tp']: trades_B_OOS.append({"pnl": state_B['tp'] - state_B['entry'], "result": "WIN"}); state_B['in'] = False
            else:
                if c['high'] >= state_B['sl']: trades_B_OOS.append({"pnl": state_B['entry'] - state_B['sl'], "result": "LOSS"}); state_B['in'] = False
                elif c['low'] <= state_B['tp']: trades_B_OOS.append({"pnl": state_B['entry'] - state_B['tp'], "result": "WIN"}); state_B['in'] = False
            if state_B['in'] and h >= 18:
                pnl = c['close'] - state_B['entry'] if state_B['dir'] == "BUY" else state_B['entry'] - c['close']
                trades_B_OOS.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"}); state_B['in'] = False
                
        if not state_B['in'] and h == 7 and b_high is not None:
            if c['close'] > b_high:
                state_B.update({'in': True, 'dir': 'BUY', 'entry': c['close'], 'sl': b_low, 'tp': c['close'] + 1.5*(b_high - b_low)})
            elif c['close'] < b_low:
                state_B.update({'in': True, 'dir': 'SELL', 'entry': c['close'], 'sl': b_high, 'tp': c['close'] - 1.5*(b_high - b_low)})

    print_results("Strategy A2 (Out-of-Sample)", trades_A2_OOS)
    print_results("Strategy B (Out-of-Sample)", trades_B_OOS)

if __name__ == '__main__': main()
