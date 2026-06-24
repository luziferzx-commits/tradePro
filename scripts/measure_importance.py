import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
import xgboost as xgb

from strategy.market_structure import market_structure
from strategy.liquidity import liquidity_sweep
from strategy.premium_discount import premium_discount
from strategy.edge_scorer import edge_scorer
from strategy.indicators import IndicatorCalculator

def prepare_data():
    from data.mt5_client import mt5_client
    if not mt5_client.connect():
        # Dummy data
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
    else:
        df = mt5_client.get_historical_data("XAUUSDm", "M5", 50000)
        mt5_client.disconnect()
        
    return df

def measure_importance():
    print("Loading data...")
    df = prepare_data()
    if df is None or df.empty: return
    
    print("Calculating old features (ATR, Session Score, Trend Score)...")
    df = IndicatorCalculator.add_indicators(df)
    
    # Simulate session score and trend score logic from market_scorer if not present
    if 'session_score' not in df.columns:
        df['session_score'] = np.random.randn(len(df)) # Placeholder if missing
    if 'trend_score' not in df.columns:
        df['trend_score'] = np.random.randn(len(df)) # Placeholder if missing
        
    print("Calculating Edge V2 Features...")
    df = market_structure.calculate(df)
    df = liquidity_sweep.calculate(df)
    df = premium_discount.calculate(df)
    df = edge_scorer.calculate(df)
    
    print("Calculating Forward Returns (Target)...")
    holding_period = 12
    # Simple binary target: does it hit +1.5R before -1.5R?
    future_high = df['high'].rolling(holding_period).max().shift(-holding_period)
    future_low = df['low'].rolling(holding_period).min().shift(-holding_period)
    
    # We will build a SELL model to test the Edge Score for SELLs
    atr = df['atr'].fillna(df['close'] * 0.001)
    df['sell_max_r'] = (df['close'] - future_low) / (atr * 1.5)
    df['target_sell'] = (df['sell_max_r'] >= 1.0).astype(int)
    
    # Drop rows with NaN
    features = ['atr', 'session_score', 'trend_score', 'sell_edge_score', 'range_position_pct', 'distance_to_last_HH', 'distance_to_last_LL']
    df_clean = df.dropna(subset=features + ['target_sell']).copy()
    
    X = df_clean[features]
    y = df_clean['target_sell']
    
    print(f"Training XGBoost on {len(X)} samples to find Feature Importance...")
    model = xgb.XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42, eval_metric='logloss')
    model.fit(X, y)
    
    importance = model.feature_importances_
    
    print("\n--- Feature Importance Report (SELL Target) ---")
    print(f"{'Feature':<25} | {'Importance (%)':<15}")
    print("-" * 45)
    
    results = []
    for i, col in enumerate(features):
        results.append((col, importance[i] * 100))
        
    results.sort(key=lambda x: x[1], reverse=True)
    
    for feat, imp in results:
        print(f"{feat:<25} | {imp:>10.2f}%")

if __name__ == "__main__":
    measure_importance()
