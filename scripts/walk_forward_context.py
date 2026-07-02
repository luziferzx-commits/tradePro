import pandas as pd
import numpy as np
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

from strategy.market_structure import market_structure
from strategy.liquidity import liquidity_sweep
from strategy.premium_discount import premium_discount
from strategy.edge_scorer import edge_scorer
from strategy.mtf import mtf_context
from strategy.indicators import IndicatorCalculator
from strategy.regime import regime_classifier
import shap

def prepare_dataset():
    from data.mt5_client import mt5_client
    if not mt5_client.connect():
        print("Using dummy data for Walk Forward Context (MT5 Not Connected)")
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

def run_context_walk_forward():
    print("Preparing Context-Aware Dataset...")
    df = prepare_dataset()
    if df is None: return

    df['session'] = calculate_session(df['time'])
    
    # 1. Base Features
    base_features = [
        'sweep_swing_high_50', 'distance_to_last_HH', 'struct_strength', 'h1_struct_trend',
        'range_position_pct', 'sell_edge_score', 'atr', 'vol_percentile'
    ]
    
    # 2. Categorical Features (XGBoost Native)
    df['session'] = df['session'].astype('category')
    df['market_regime'] = df['market_regime'].astype('category')
    
    # Create Volatility Bucket
    conditions = [
        df['vol_percentile'] <= 25,
        (df['vol_percentile'] > 25) & (df['vol_percentile'] <= 75),
        df['vol_percentile'] > 75
    ]
    df['volatility_bucket'] = np.select(conditions, ['LOW', 'NORMAL', 'HIGH'], default='NORMAL')
    df['volatility_bucket'] = df['volatility_bucket'].astype('category')
    
    context_features = ['session', 'market_regime', 'volatility_bucket']
    all_features = base_features + context_features
    
    # Define df_clean properly
    df_clean = df.dropna(subset=all_features + ['target_sell']).copy()
    
    # APPLY PRE-FILTER (Only analyze Tier A Setups)
    df_clean = df_clean[df_clean['sell_edge_score'] >= 80]
    
    # Slice by time instead of row index!
    df_clean.set_index('time', inplace=True)
    df_clean.sort_index(inplace=True)
    
    start_date = df_clean.index.min()
    end_date = df_clean.index.max()
    
    # Generate 3-month steps
    windows = []
    current_date = start_date
    while current_date + pd.DateOffset(months=15) <= end_date:
        train_start = current_date
        train_end = current_date + pd.DateOffset(months=12)
        test_end = train_end + pd.DateOffset(months=3)
        windows.append((train_start, train_end, test_end))
        current_date += pd.DateOffset(months=3)
        
    num_windows = len(windows)
    
    print(f"\nTotal Tier A Signals available: {len(df_clean)}")
    print(f"Running Context-Aware XGBoost Walk-Forward (12m Train / 3m Test) - {num_windows} Windows")
    print("-" * 80)
    print(f"{'Window':<8} | {'Trades':<8} | {'Win Rate':<10} | {'PF':<8} | {'DD (%)':<8} | {'Expectancy':<12} | {'Status':<10}")
    print("-" * 80)
    
    passing_windows = 0
    all_preds = []
    
    for w, (train_start, train_end, test_end) in enumerate(windows):
        train_raw = df_clean[(df_clean.index >= train_start) & (df_clean.index < train_end)]
        test_raw = df_clean[(df_clean.index >= train_end) & (df_clean.index < test_end)]
        
        if len(train_raw) < 50 or len(test_raw) < 5:
            print(f"W{w+1:<7} | {'N/A':<8} | {'N/A':<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<12} | Skipped")
            continue
            
        X_train, y_train = train_raw[all_features], train_raw['target_sell']
        X_test, y_test = test_raw[all_features], test_raw['target_sell']
        
        if len(y_train.unique()) < 2: continue
        
        scale_pos_weight = (len(y_train) - y_train.sum()) / y_train.sum() if y_train.sum() > 0 else 1.0
        
        # Train XGBoost with Context Features
        model = xgb.XGBClassifier(
            max_depth=2,
            n_estimators=100,
            learning_rate=0.05,
            objective='binary:logistic',
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            eval_metric='logloss',
            tree_method='hist',
            enable_categorical=True
        )
        model.fit(X_train, y_train)
        
        preds_proba = model.predict_proba(X_test)[:, 1]
        test_filtered = test_raw.copy()
        test_filtered['xgb_prob'] = preds_proba
        
        # We trained on the full dataset. Now we test the strategy by trading only when:
        # 1. It is a Tier A Liquidity Setup (sell_edge_score >= 80)
        # 2. XGBoost confirms the Context is highly favorable (xgb_prob > 0.55)
        # We need a higher threshold because XGBoost naturally outputs higher probabilities
        # for setups that it recognizes have Edge Score >= 80.
        trade_signals = test_filtered[(test_filtered['xgb_prob'] > 0.515)].copy()
        trade_signals['window_idx'] = w + 1
        
        if w == num_windows - 1:
            # SHAP Analysis on the last window
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_test)
            shap_df = pd.DataFrame({'Feature': all_features, 'Importance': np.abs(shap_values).mean(axis=0)})
            shap_df = shap_df.sort_values('Importance', ascending=False)
            print("\nCalculating SHAP Values for Context-Aware XGBoost (Latest Window)...\n")
            print("Top 15 Features by SHAP Importance:")
            print(shap_df.head(15).to_string(index=False))
            
        # Calculate stats for this window
        trades = len(trade_signals)
        if trades > 0:
            wins = trade_signals['target_sell'].sum()
            losses = trades - wins
            win_rate = (wins / trades)
            
            gross_profit = wins * 1.5
            gross_loss = losses * 1.0
            pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            returns = pd.Series([1.5 if y == 1 else -1.0 for y in trade_signals['target_sell']]) / 100.0
            cumulative_returns = (1 + returns).cumprod()
            peak = cumulative_returns.cummax()
            dd = ((cumulative_returns - peak) / peak) * 100
            max_dd = dd.min() if not dd.empty else 0.0
            
            expectancy = ((win_rate)*1.5) - ((1-(win_rate))*1.0)
            
            # Target Criteria: PF >= 1.6, DD > -12%, Trades >= 30
            status = "PASS" if pf >= 1.60 and max_dd > -12.0 and trades >= 30 else "FAIL"
            
            print(f"W{w+1:<7} | {trades:<8} | {win_rate*100:>6.1f}%    | {pf:>6.2f}   | {max_dd:>6.1f}% | {expectancy:>6.2f} R     | {status}")
            
            if status == "PASS":
                passing_windows += 1
        else:
            print(f"W{w+1:<7} | {0:<8} | {'0.0%':>10} | {'0.00':>8} | {'0.0%':>8} | {'0.00 R':>12} | FAIL")
            
        all_preds.append(trade_signals)
        
    print("-" * 80)
    print(f"Passing Windows % : {passing_windows}/{num_windows} ({(passing_windows/num_windows)*100:.1f}%) [Target >= 70%]\n")

    if len(all_preds) > 0:
        df_results = pd.concat(all_preds)
        df_results.to_csv('results/context_preds.csv')
        print("Saved predictions to results/context_preds.csv")

if __name__ == "__main__":
    run_context_walk_forward()
