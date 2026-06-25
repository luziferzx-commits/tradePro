import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from strategy.market_structure import market_structure
from strategy.liquidity import liquidity_sweep
from strategy.premium_discount import premium_discount
from strategy.indicators import IndicatorCalculator

def calculate_forward_r(df, holding_period=12, stop_loss_atr=1.5):
    """
    Simulates a trade taken at the close of the current candle.
    Returns:
    - win_rate: Did it reach +1.5R before -1.5R? (Simplified to: Max High > entry + 1.5ATR)
    - max_r: Maximum R reached during the holding period.
    - mae_r: Maximum Adverse Excursion (Drawdown) in R during the holding period.
    """
    res = df.copy()
    
    # Calculate ATR for R normalization
    res = IndicatorCalculator.add_indicators(res)
    atr = res['atr'].fillna(res['close'] * 0.001) # fallback
    
    # Forward features
    # For a BUY signal
    future_high = res['high'].rolling(holding_period).max().shift(-holding_period)
    future_low = res['low'].rolling(holding_period).min().shift(-holding_period)
    
    # R calculations for BUY
    res['buy_max_r'] = (future_high - res['close']) / (atr * stop_loss_atr)
    res['buy_mae_r'] = (res['close'] - future_low) / (atr * stop_loss_atr) # positive MAE means price went down
    res['buy_win'] = res['buy_max_r'] >= 1.0 # arbitrary threshold
    
    # R calculations for SELL
    res['sell_max_r'] = (res['close'] - future_low) / (atr * stop_loss_atr)
    res['sell_mae_r'] = (future_high - res['close']) / (atr * stop_loss_atr)
    res['sell_win'] = res['sell_max_r'] >= 1.0
    
    return res

def validate_features():
    print("Loading historical data for XAUUSDm...")
    from data.mt5_client import mt5_client
    if not mt5_client.connect():
        print("MT5 Connection Failed. Using dummy data for testing.")
        # Create dummy data if MT5 is not available
        dates = pd.date_range("2023-01-01", periods=10000, freq="5min")
        np.random.seed(42)
        close = 2000 + np.random.randn(10000).cumsum()
        df = pd.DataFrame({
            'time': dates,
            'open': close + np.random.randn(10000)*0.5,
            'high': close + np.abs(np.random.randn(10000)),
            'low': close - np.abs(np.random.randn(10000)),
            'close': close,
            'tick_volume': 100
        })
    else:
        df = mt5_client.get_historical_data("XAUUSDm", "M5", 50000)
        mt5_client.disconnect()
        
    if df is None or df.empty:
        print("No data available.")
        return
        
    print(f"Data loaded: {len(df)} candles.")
    
    print("Calculating Features...")
    df = market_structure.calculate(df)
    df = liquidity_sweep.calculate(df)
    df = premium_discount.calculate(df)
    
    print("Calculating Forward Returns (Holding Period: 12 candles)...")
    df = calculate_forward_r(df, holding_period=12)
    
    # Drop NaNs
    df.dropna(subset=['buy_max_r', 'struct_trend'], inplace=True)
    
    print("\n--- Feature Validation Report ---")
    print(f"{'Feature':<30} | {'Occurrences':<12} | {'Win Rate':<10} | {'Avg R':<8} | {'Max DD (MAE)':<15}")
    print("-" * 85)
    
    print("\n--- Feature Interaction Report (Top 20 Combinations) ---")
    print(f"{'Combo':<50} | {'Occurrences':<12} | {'Win Rate':<10} | {'Avg R':<8} | {'Expectancy':<10}")
    print("-" * 100)
    
    # Define our base signals
    buy_signals = {
        'Uptrend': df['struct_trend'] == "UPTREND",
        'Sweep Daily Low': df['sweep_daily_low'],
        'Sweep Swing Low 50': df['sweep_swing_low_50'],
        'Discount Zone': df['is_discount_zone']
    }
    
    sell_signals = {
        'Downtrend': df['struct_trend'] == "DOWNTREND",
        'Sweep Daily High': df['sweep_daily_high'],
        'Sweep Swing High 50': df['sweep_swing_high_50'],
        'Premium Zone': df['is_premium_zone']
    }
    
    import itertools
    results = []
    
    # Function to evaluate and store combo
    def evaluate_combo(name, condition, direction):
        subset = df[condition]
        occurrences = len(subset)
        if occurrences < 50: # Filter out noise
            return
            
        if direction == 'BUY':
            win_rate = subset['buy_win'].mean()
            avg_r = subset['buy_max_r'].mean()
        else:
            win_rate = subset['sell_win'].mean()
            avg_r = subset['sell_max_r'].mean()
            
        # Expectancy: Assuming TP is 1.5R, SL is 1.0R (actually my buy_win uses >= 1.0)
        # Let's just use Avg R as a proxy for Expectancy, or calculate Expectancy = WinRate * AvgWinR - LossRate * 1.0
        # For simplicity, Expectancy = win_rate * 1.5 - (1 - win_rate) * 1.0
        expectancy = (win_rate * 1.5) - ((1 - win_rate) * 1.0)
        
        results.append({
            'Combo': f"{name} ({direction})",
            'Occurrences': occurrences,
            'Win Rate': win_rate * 100,
            'Avg R': avg_r,
            'Expectancy': expectancy
        })

    # Generate Combinations for BUY
    buy_names = list(buy_signals.keys())
    for r in range(1, 4): # 1, 2, 3 feature combos
        for combo in itertools.combinations(buy_names, r):
            name = " + ".join(combo)
            condition = buy_signals[combo[0]]
            for c in combo[1:]:
                condition = condition & buy_signals[c]
            evaluate_combo(name, condition, 'BUY')
            
    # Generate Combinations for SELL
    sell_names = list(sell_signals.keys())
    for r in range(1, 4):
        for combo in itertools.combinations(sell_names, r):
            name = " + ".join(combo)
            condition = sell_signals[combo[0]]
            for c in combo[1:]:
                condition = condition & sell_signals[c]
            evaluate_combo(name, condition, 'SELL')
            
    # Sort by Expectancy descending
    results.sort(key=lambda x: x['Expectancy'], reverse=True)
    
    # Print Top 20
    for res in results[:20]:
        print(f"{res['Combo']:<50} | {res['Occurrences']:<12} | {res['Win Rate']:>8.1f}% | {res['Avg R']:>8.2f} | {res['Expectancy']:>8.2f} R")

    print("-" * 100)

if __name__ == "__main__":
    validate_features()
