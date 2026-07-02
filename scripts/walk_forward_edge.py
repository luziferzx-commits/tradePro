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

from strategy.regime import regime_classifier

def prepare_dataset():
    from data.mt5_client import mt5_client
    if not mt5_client.connect():
        # Generate 250,000 candles (approx 3.5 years of M5 data)
        print("Using dummy data for Walk Forward (MT5 Not Connected)")
        dates = pd.date_range("2021-01-01", periods=250000, freq="5min")
        np.random.seed(42)
        close = 2000 + np.random.randn(250000).cumsum()
        df = pd.DataFrame({
            'time': dates,
            'open': close + np.random.randn(250000)*0.5,
            'high': close + np.abs(np.random.randn(250000)),
            'low': close - np.abs(np.random.randn(250000)),
            'close': close,
            'tick_volume': 100
        })
    else:
        print("Fetching 250,000 candles from MT5...")
        df = mt5_client.get_historical_data("XAUUSDm", "M5", 250000)
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
    df = regime_classifier.calculate(df)
    
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

def calculate_session(time_series):
    hour = time_series.dt.hour
    conditions = [
        (hour >= 13) & (hour < 22),
        (hour >= 8) & (hour < 13),
        (hour < 8) | (hour >= 22)
    ]
    choices = ['NY', 'London', 'Asia']
    return np.select(conditions, choices, default='Asia')

def calculate_max_dd(returns):
    cum_returns = (1 + returns).cumprod()
    peak = cum_returns.cummax()
    drawdown = (cum_returns - peak) / peak
    return drawdown.min() * 100

def run_walk_forward():
    print("Preparing Full Edge V2 Dataset (approx 3.5 years)...")
    df = prepare_dataset()
    if df is None: return

    df['session'] = calculate_session(df['time'])
    
    # We apply the Regime Filter directly
    print("Applying Optimal Regime Filter: London Session OR (Asia + CONTRACTING)")
    df['is_optimal_regime'] = (df['session'] == 'London') | ((df['session'] == 'Asia') & (df['market_regime'] == 'CONTRACTING'))
    
    features = [
        'sweep_swing_high_50', 'sweep_swing_low_50', 'sweep_daily_high',
        'distance_to_last_HH', 'distance_to_last_LL', 'struct_strength', 'h1_struct_trend',
        'range_position_pct', 'sell_edge_score', 'buy_edge_score',
        'atr', 'session_score', 'trend_score'
    ]
    
    df_clean = df.dropna(subset=features + ['target_sell', 'market_regime', 'session']).copy()
    
    # 1 Year M5 = ~72,000 candles. 3 Months M5 = ~18,000 candles
    train_size = 72000
    test_size = 18000
    step_size = 18000
    
    total_samples = len(df_clean)
    num_windows = (total_samples - train_size) // step_size
    
    print(f"\nTotal M5 Candles available: {total_samples}")
    print(f"Running Robust Walk-Forward (Train 12m, Test 3m) - {num_windows} Windows")
    print("-" * 80)
    print(f"{'Window':<8} | {'Trades':<8} | {'Win Rate':<10} | {'PF':<8} | {'DD (%)':<8} | {'Expectancy':<12} | {'Status':<10}")
    print("-" * 80)
    
    passing_windows = 0
    
    for w in range(num_windows):
        start_idx = w * step_size
        train_end_idx = start_idx + train_size
        test_end_idx = train_end_idx + test_size
        
        # Slicing the RAW chronological timeline
        train_raw = df_clean.iloc[start_idx:train_end_idx]
        test_raw = df_clean.iloc[train_end_idx:test_end_idx]
        
        # APPLY TIER A + REGIME FILTER BEFORE ML
        train_filtered = train_raw[(train_raw['sell_edge_score'] >= 80) & (train_raw['is_optimal_regime'] == True)]
        test_filtered = test_raw[(test_raw['sell_edge_score'] >= 80) & (test_raw['is_optimal_regime'] == True)]
        
        if len(train_filtered) < 20 or len(test_filtered) < 5:
            print(f"W{w+1:<7} | {'N/A':<8} | {'N/A':<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<12} | Skipped")
            continue
            
        X_train = train_filtered[features]
        y_train = train_filtered['target_sell']
        X_test = test_filtered[features]
        y_test = test_filtered['target_sell']
        
        model = xgb.XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train)
        
        preds = model.predict_proba(X_test)[:, 1]
        trade_signals = preds >= 0.55
        
        total_trades = trade_signals.sum()
        if total_trades == 0:
            print(f"W{w+1:<7} | 0        | 0.0%       | 0.00     | 0.0      | 0.00 R       | FAIL")
            continue
            
        wins = (trade_signals & (y_test == 1)).sum()
        losses = total_trades - wins
        win_rate = (wins / total_trades) * 100
        
        gross_profit = wins * 1.5
        gross_loss = losses * 1.0
        pf = gross_profit / gross_loss if gross_loss > 0 else 999.0
        expectancy = ((win_rate/100)*1.5) - ((1-(win_rate/100))*1.0)
        
        # Simulate returns for DD
        # Each trade risks 1% of account
        returns = pd.Series([1.5 if y == 1 else -1.0 for y in y_test[trade_signals]]) / 100.0
        dd = calculate_max_dd(returns)
        
        # Passing Logic: PF > 1.60 and DD > -12%
        is_pass = (pf > 1.60) and (dd > -12.0)
        if is_pass: passing_windows += 1
        
        status_str = "PASS" if is_pass else "FAIL"
        
        print(f"W{w+1:<7} | {total_trades:<8} | {win_rate:>6.1f}%    | {pf:>6.2f}   | {dd:>6.1f}% | {expectancy:>6.2f} R     | {status_str}")

    pass_rate = (passing_windows / num_windows) * 100 if num_windows > 0 else 0
    print("-" * 80)
    print(f"Passing Windows % : {passing_windows}/{num_windows} ({pass_rate:.1f}%) [Target >= 70%]")

if __name__ == "__main__":
    run_walk_forward()
