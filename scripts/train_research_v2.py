import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
import xgboost as xgb
import shap

from strategy.market_structure import market_structure
from strategy.liquidity import liquidity_sweep
from strategy.premium_discount import premium_discount
from strategy.edge_scorer import edge_scorer
from strategy.mtf import mtf_context
from strategy.indicators import IndicatorCalculator

def prepare_dataset():
    from data.mt5_client import mt5_client
    if not mt5_client.connect():
        print("Using dummy data for train_research_v2")
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
        # Fetch 100k for Train + Walk Forward
        df = mt5_client.get_historical_data("XAUUSDm", "M5", 100000)
        mt5_client.disconnect()
        
    if df is None or df.empty: return None

    # V1 Features
    df = IndicatorCalculator.add_indicators(df)
    if 'session_score' not in df.columns: df['session_score'] = np.random.randn(len(df))
    if 'trend_score' not in df.columns: df['trend_score'] = np.random.randn(len(df))
    
    # V2 Features
    df = mtf_context.calculate(df)
    df = market_structure.calculate(df)
    df = liquidity_sweep.calculate(df)
    df = premium_discount.calculate(df)
    df = edge_scorer.calculate(df)
    
    # Labeling (Holding Period = 12 M5 = 1H)
    holding_period = 12
    sl_atr = 1.0
    tp_atr = 1.5
    atr = df['atr'].fillna(df['close'] * 0.001)
    
    future_high = df['high'].rolling(holding_period).max().shift(-holding_period)
    future_low = df['low'].rolling(holding_period).min().shift(-holding_period)
    
    # BUY TARGET
    buy_tp = df['close'] + (atr * tp_atr)
    buy_win = future_high >= buy_tp
    df['target_buy'] = buy_win.astype(int)
    
    # SELL TARGET
    sell_tp = df['close'] - (atr * tp_atr)
    sell_win = future_low <= sell_tp
    df['target_sell'] = sell_win.astype(int)
    
    # Filter Expectancy <= 0 (e.g., sweep_daily_low)
    # We simply drop the weak columns so the model cannot use them.
    drop_cols = ['sweep_daily_low'] 
    df.drop(columns=drop_cols, inplace=True, errors='ignore')

    return df

def train_and_evaluate():
    print("Preparing Full Edge V2 Dataset...")
    df = prepare_dataset()
    if df is None: return

    # Define Feature Categories for SHAP
    categories = {
        'Liquidity': ['sweep_swing_high_50', 'sweep_swing_low_50', 'sweep_daily_high'],
        'Structure': ['distance_to_last_HH', 'distance_to_last_LL', 'struct_strength', 'h1_struct_trend'],
        'Premium/Discount': ['range_position_pct'],
        'Edge Score': ['sell_edge_score', 'buy_edge_score'],
        'Legacy': ['atr', 'session_score', 'trend_score']
    }

    # Flatten feature list
    features = []
    for k, v in categories.items():
        for feat in v:
            if feat in df.columns:
                features.append(feat)

    # We will build the SELL model for the Walk Forward Test
    # Convert string features to numerical if necessary (h1_struct_trend)
    if 'h1_struct_trend' in df.columns:
        df['h1_struct_trend'] = np.where(df['h1_struct_trend'] == 'UPTREND', 1,
                                np.where(df['h1_struct_trend'] == 'DOWNTREND', -1, 0))
                                
    if 'struct_strength' in df.columns:
        df['struct_strength'] = np.where(df['struct_strength'] == 'STRONG', 1, 0)
        
    df_clean = df.dropna(subset=features + ['target_sell']).copy()
    
    # Train / Test Split (Walk Forward)
    # 70% Train, 30% Walk Forward
    split_idx = int(len(df_clean) * 0.7)
    train_df = df_clean.iloc[:split_idx]
    test_df = df_clean.iloc[split_idx:]
    
    X_train = train_df[features]
    y_train = train_df['target_sell']
    X_test = test_df[features]
    y_test = test_df['target_sell']
    
    print(f"Training Candidate v2 (XGBoost) on {len(X_train)} samples...")
    model = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42)
    model.fit(X_train, y_train)
    
    # -----------------------------------
    # 1. SHAP Dominance Test
    # -----------------------------------
    print("\nCalculating SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_train)
    
    # Mean absolute SHAP values per feature
    if isinstance(shap_values, list): shap_values = shap_values[1] # For binary classification
    shap_abs = np.abs(shap_values).mean(axis=0)
    
    # Map to categories
    shap_dict = {feat: val for feat, val in zip(features, shap_abs)}
    total_shap = sum(shap_dict.values())
    
    cat_importance = {}
    for cat, feats in categories.items():
        cat_sum = sum([shap_dict.get(f, 0) for f in feats])
        cat_importance[cat] = (cat_sum / total_shap) * 100 if total_shap > 0 else 0
        
    print("\n--- SHAP Dominance by Category ---")
    for cat, imp in sorted(cat_importance.items(), key=lambda x: x[1], reverse=True):
        print(f"{cat:<20} | {imp:>5.1f}%")
        
    edge_v2_total = cat_importance.get('Liquidity', 0) + cat_importance.get('Structure', 0) + cat_importance.get('Premium/Discount', 0) + cat_importance.get('Edge Score', 0)
    print(f"\nTotal Edge V2 SHAP Dominance: {edge_v2_total:.1f}% (> 25% Required)")
    
    # -----------------------------------
    # 2. Walk Forward Test
    # -----------------------------------
    print("\n--- Walk Forward Backtest (Test Set 30%) ---")
    preds = model.predict_proba(X_test)[:, 1]
    
    # Execution threshold
    threshold = 0.55
    trade_signals = preds >= threshold
    
    total_trades = trade_signals.sum()
    wins = (trade_signals & (y_test == 1)).sum()
    losses = total_trades - wins
    
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    # Assuming 1:1.5 RR
    gross_profit = wins * 1.5
    gross_loss = losses * 1.0
    pf = gross_profit / gross_loss if gross_loss > 0 else 999.0
    
    print(f"Profit Factor (PF): {pf:.2f} (Target > 1.60)")
    print(f"Win Rate:           {win_rate:.1f}%")
    print(f"Total Trades:       {total_trades}")
    print(f"Expectancy:         {((win_rate/100)*1.5) - ((1-(win_rate/100))*1.0):.2f} R")
    print("\nNote: Max DD is skipped in this quick script, but PF indicates profitability.")

if __name__ == "__main__":
    train_and_evaluate()
