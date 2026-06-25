import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from strategy.strategies.registry import StrategyRegistry
from strategy.strategies.ensemble_router import EnsembleRouter
from market.regime_detector import RegimeDetector

def calculate_metrics(trades, initial_capital=10000.0):
    if not trades:
        return {"total": 0}
        
    capital = initial_capital
    peak = capital
    max_dd_pct = 0.0
    wins, losses = [], []
    
    for t in trades:
        capital += t['pnl']
        if capital > peak: peak = capital
        dd_pct = (peak - capital) / peak * 100
        if dd_pct > max_dd_pct: max_dd_pct = dd_pct
            
        if t['result'] == 'WIN': wins.append(t)
        else: losses.append(t)
            
    total_trades = len(trades)
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else 999.99
    
    pnls = [t['pnl'] for t in trades]
    sharpe = (np.mean(pnls) / np.std(pnls)) * np.sqrt(252) if np.std(pnls) > 0 and len(pnls) > 1 else 0.0
    
    avg_win = gross_profit / len(wins) if wins else 0
    avg_loss = gross_loss / len(losses) if losses else 0
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    return {
        "total": total_trades,
        "win_rate": win_rate,
        "pf": pf,
        "max_dd": max_dd_pct,
        "sharpe": sharpe,
        "rr": rr_ratio,
        "avg_win": avg_win,
        "avg_loss": avg_loss
    }

def print_metrics(name, metrics):
    print(f"\n--- {name} ---")
    if metrics['total'] == 0:
        print("No trades.")
        return
    print(f"Total Trades: {metrics['total']}")
    print(f"Win Rate: {metrics['win_rate']:.1f}%")
    print(f"Profit Factor: {metrics['pf']:.2f}")
    print(f"Avg Win: {metrics['avg_win']:.2f} | Avg Loss: {metrics['avg_loss']:.2f} | RR: {metrics['rr']:.2f}")
    print(f"Max DD: {metrics['max_dd']:.2f}%")
    print(f"Sharpe: {metrics['sharpe']:.2f}")

def main():
    symbol = "XAUUSD"
    if not mt5_client.connect(): return
        
    print("Fetching historical data...")
    df = mt5_client.get_historical_data(symbol, "M5", 100000)
    df = IndicatorCalculator.add_indicators(df)
    
    registry = StrategyRegistry(symbol, "M5")
    router = EnsembleRouter(trading_cost_r=0.1, min_ev_threshold=0.0)
    
    trades_router = []
    
    print("Running Ensemble Router Backtest...")
    
    # Simulate step by step (simplified simulation for speed, just evaluating signals)
    # A full robust backtester would iterate candle by candle and track open positions.
    # Here we are just identifying the router's signals to prove the pipeline works.
    
    # We will slice data incrementally to simulate live environment
    records = df.to_dict('records')
    in_trade = False
    trade_dir = None
    entry_price = 0.0
    sl = 0.0
    tp = 0.0
    
    # Slicing is slow, let's just use regime from full DF for now to speed up the proof-of-concept
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    
    for i in range(500, len(records) - 1):
        c = records[i]
        
        if in_trade:
            if trade_dir == "BUY":
                if c['low'] <= sl: trades_router.append({"pnl": sl - entry_price, "result": "LOSS"}); in_trade = False
                elif c['high'] >= tp: trades_router.append({"pnl": tp - entry_price, "result": "WIN"}); in_trade = False
            else:
                if c['high'] >= sl: trades_router.append({"pnl": entry_price - sl, "result": "LOSS"}); in_trade = False
                elif c['low'] <= tp: trades_router.append({"pnl": entry_price - tp, "result": "WIN"}); in_trade = False
            continue
            
        # We need a regime dictionary. Let's mock a basic one to avoid recalculating regime every candle
        mock_regime = {
            "is_high_volatility": c.get('adx', 0) > 25,
            "is_ranging": c.get('adx', 0) < 25,
            "is_trending_up": c.get('ema50_slope', 0) > 0.5,
            "is_trending_down": c.get('ema50_slope', 0) < -0.5
        }
        
        # We create a slice of the dataframe up to this point
        # For performance in this test script, we pass the current row disguised as a DF
        # Actually, BaseStrategy uses `latest = df.iloc[-1]`. 
        # Passing df.iloc[:i] is extremely slow for 100k rows. 
        # Let's pass a small slice `df.iloc[i-50:i]`
        df_slice = df.iloc[i-50:i+1]
        
        signal = router.route(df_slice, mock_regime, registry)
        
        if signal.direction != "NEUTRAL":
            in_trade = True
            trade_dir = signal.direction
            entry_price = signal.entry_price
            sl = signal.stop_loss
            tp = signal.take_profit
            
    metrics = calculate_metrics(trades_router)
    print_metrics("Ensemble Router Validation", metrics)

if __name__ == '__main__': main()
