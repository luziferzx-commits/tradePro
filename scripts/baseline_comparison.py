import pandas as pd
import numpy as np

def prepare_data():
    from strategy.market_structure import market_structure
    from strategy.liquidity import liquidity_sweep
    from strategy.premium_discount import premium_discount
    from strategy.edge_scorer import edge_scorer
    from data.mt5_client import mt5_client
    
    if mt5_client.connect():
        df = mt5_client.get_historical_data("XAUUSDm", "M5", 50000)
        mt5_client.disconnect()
    else:
        print("Using dummy data")
        dates = pd.date_range("2023-01-01", periods=50000, freq="5min")
        np.random.seed(42)
        close = 2000 + np.random.randn(50000).cumsum()
        df = pd.DataFrame({
            'time': dates,
            'open': close + np.random.randn(50000)*0.5,
            'high': close + np.abs(np.random.randn(50000)),
            'low': close - np.abs(np.random.randn(50000)),
            'close': close,
            'tick_volume': 100
        })

    if df is None or df.empty: return None

    df = market_structure.calculate(df)
    df = liquidity_sweep.calculate(df)
    df = premium_discount.calculate(df)
    df = edge_scorer.calculate(df)
    
    # Simple ATR
    df['atr'] = (df['high'] - df['low']).rolling(14).mean().fillna(df['close'] * 0.001)
    
    return df

def run_backtest():
    print("Loading data and calculating features...")
    df = prepare_data()
    if df is None: return
    
    # We simulate a strict mechanical rule:
    # BUY if buy_edge_score >= 80
    # SELL if sell_edge_score >= 80
    
    holding_period = 12
    sl_atr = 1.0
    tp_atr = 1.5
    
    future_high = df['high'].rolling(holding_period).max().shift(-holding_period)
    future_low = df['low'].rolling(holding_period).min().shift(-holding_period)
    
    # Determine trade outcomes for every possible bar
    # A positive outcome means it hit +1.5R before -1.0R (simplified as just reaching TP)
    buy_tp = df['close'] + (df['atr'] * tp_atr)
    buy_sl = df['close'] - (df['atr'] * sl_atr)
    buy_win = future_high >= buy_tp
    
    sell_tp = df['close'] - (df['atr'] * tp_atr)
    sell_sl = df['close'] + (df['atr'] * sl_atr)
    sell_win = future_low <= sell_tp
    
    # Now apply the Edge Score Rule
    buy_signals = df['buy_edge_score'] >= 80
    sell_signals = df['sell_edge_score'] >= 80
    
    total_buy_trades = buy_signals.sum()
    buy_wins = (buy_signals & buy_win).sum()
    buy_losses = total_buy_trades - buy_wins
    
    total_sell_trades = sell_signals.sum()
    sell_wins = (sell_signals & sell_win).sum()
    sell_losses = total_sell_trades - sell_wins
    
    total_trades = total_buy_trades + total_sell_trades
    total_wins = buy_wins + sell_wins
    total_losses = total_trades - total_wins
    
    win_rate = (total_wins / total_trades) * 100 if total_trades > 0 else 0
    
    # Calculate Profit Factor
    # Gross Profit = total_wins * 1.5R
    # Gross Loss = total_losses * 1.0R
    gross_profit = total_wins * 1.5
    gross_loss = total_losses * 1.0
    pf = gross_profit / gross_loss if gross_loss > 0 else 999.0
    
    print("\n--- Edge Score V1 Baseline Comparison ---")
    print(f"{'Metric':<20} | {'Current Candidate':<20} | {'Edge Score Rule Only':<20}")
    print("-" * 65)
    print(f"{'Profit Factor (PF)':<20} | {'~ 1.47':<20} | {pf:<20.2f}")
    print(f"{'Win Rate':<20} | {'~ 56.48%':<20} | {win_rate:<20.1f}%")
    print(f"{'Trades Count':<20} | {'N/A (Reference)':<20} | {total_trades:<20}")
    print("-" * 65)
    print("Note: This assumes a fixed 1:1.5 Risk-Reward ratio without any XGBoost filtering.")

if __name__ == "__main__":
    run_backtest()
