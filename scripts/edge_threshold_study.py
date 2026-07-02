import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
import xgboost as xgb

from strategy.market_structure import market_structure
from strategy.liquidity import liquidity_sweep
from strategy.premium_discount import premium_discount
from strategy.edge_scorer import edge_scorer
from strategy.mtf import mtf_context
from strategy.indicators import IndicatorCalculator

def prepare_dataset():
    from data.mt5_client import mt5_client
    if not mt5_client.connect():
        dates = pd.date_range("2023-01-01", periods=100000, freq="5min")
        np.random.seed(42)
        close = 2000 + np.random.randn(100000).cumsum()
        df = pd.DataFrame({
            'time': dates,
            'open': close + np.random.randn(100000)*0.5,
            'high': close + np.abs(np.random.randn(100000)),
            'low': close - np.abs(np.random.randn(100000)),
            'close': close,
            'tick_volume': 100
        })
    else:
        df = mt5_client.get_historical_data("XAUUSDm", "M5", 100000)
        mt5_client.disconnect()
        
    if df is None or df.empty: return None

    df = IndicatorCalculator.add_indicators(df)
    if 'session_score' not in df.columns: df['session_score'] = np.random.randn(len(df))
    if 'trend_score' not in df.columns: df['trend_score'] = np.random.randn(len(df))
    
    df = mtf_context.calculate(df)
    df = market_structure.calculate(df)
    df = liquidity_sweep.calculate(df)
    df = premium_discount.calculate(df)
    df = edge_scorer.calculate(df)
    
    holding_period = 12
    sl_atr = 1.0
    tp_atr = 1.5
    atr = df['atr'].fillna(df['close'] * 0.001)
    
    future_low = df['low'].rolling(holding_period).min().shift(-holding_period)
    sell_tp = df['close'] - (atr * tp_atr)
    sell_win = future_low <= sell_tp
    df['target_sell'] = sell_win.astype(int)
    
    if 'h1_struct_trend' in df.columns:
        df['h1_struct_trend'] = np.where(df['h1_struct_trend'] == 'UPTREND', 1,
                                np.where(df['h1_struct_trend'] == 'DOWNTREND', -1, 0))
    if 'struct_strength' in df.columns:
        df['struct_strength'] = np.where(df['struct_strength'] == 'STRONG', 1, 0)

    drop_cols = ['sweep_daily_low'] 
    df.drop(columns=drop_cols, inplace=True, errors='ignore')

    return df

def run_study():
    print("Preparing Dataset...")
    df = prepare_dataset()
    if df is None: return

    features = [
        'sweep_swing_high_50', 'sweep_swing_low_50', 'sweep_daily_high',
        'distance_to_last_HH', 'distance_to_last_LL', 'struct_strength', 'h1_struct_trend',
        'range_position_pct', 'sell_edge_score', 'buy_edge_score',
        'atr', 'session_score', 'trend_score'
    ]
    
    df_clean = df.dropna(subset=features + ['target_sell']).copy()
    split_idx = int(len(df_clean) * 0.7)
    
    filters = {
        'All Data': pd.Series([True] * len(df_clean), index=df_clean.index),
        'Edge Score >= 60': df_clean['sell_edge_score'] >= 60,
        'Edge Score >= 70': df_clean['sell_edge_score'] >= 70,
        'Edge Score >= 80': df_clean['sell_edge_score'] >= 80,
        'Triple Crown Only': (df_clean['sell_edge_score'] >= 90) # Approximates Sweep + Premium + Downtrend
    }

    print(f"\\n{'Filter (SELL Model)':<20} | {'Train Samples':<15} | {'Test Samples':<15} | {'Win Rate':<10} | {'PF':<8} | {'Expectancy':<12}")
    print("-" * 95)

    for name, condition in filters.items():
        df_filtered = df_clean[condition]
        
        # Split based on time to maintain Walk-Forward integrity
        train_df = df_filtered[df_filtered.index < df_clean.index[split_idx]]
        test_df = df_filtered[df_filtered.index >= df_clean.index[split_idx]]
        
        if len(train_df) < 50 or len(test_df) < 20:
            print(f"{name:<20} | {len(train_df):<15} | {len(test_df):<15} | {'N/A (Too few samples)':<35}")
            continue
            
        X_train = train_df[features]
        y_train = train_df['target_sell']
        X_test = test_df[features]
        y_test = test_df['target_sell']
        
        model = xgb.XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train)
        
        preds = model.predict_proba(X_test)[:, 1]
        trade_signals = preds >= 0.55
        
        total_trades = trade_signals.sum()
        if total_trades == 0:
            print(f"{name:<20} | {len(train_df):<15} | {len(test_df):<15} | {'0.0%':<10} | {'0.00':<8} | {'0.00 R':<12}")
            continue
            
        wins = (trade_signals & (y_test == 1)).sum()
        losses = total_trades - wins
        
        win_rate = (wins / total_trades * 100)
        gross_profit = wins * 1.5
        gross_loss = losses * 1.0
        pf = gross_profit / gross_loss if gross_loss > 0 else 999.0
        expectancy = ((win_rate/100)*1.5) - ((1-(win_rate/100))*1.0)
        
        print(f"{name:<20} | {len(train_df):<15} | {len(test_df):<15} | {win_rate:>8.1f}% | {pf:>8.2f} | {expectancy:>8.2f} R")

if __name__ == "__main__":
    run_study()
