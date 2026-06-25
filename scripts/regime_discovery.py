import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from strategy.market_structure import market_structure
from strategy.liquidity import liquidity_sweep
from strategy.premium_discount import premium_discount
from strategy.edge_scorer import edge_scorer
from strategy.mtf import mtf_context
from strategy.indicators import IndicatorCalculator
from strategy.regime import regime_classifier

def prepare_dataset():
    from data.mt5_client import mt5_client
    if not mt5_client.connect(): return None
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

    return df

def calculate_max_dd(returns):
    cum_returns = (1 + returns).cumprod()
    peak = cum_returns.cummax()
    drawdown = (cum_returns - peak) / peak
    return drawdown.min() * 100

def calculate_session(time_series):
    hour = time_series.dt.hour
    # Assuming UTC
    # Asia: 0-8, London: 8-13, NY: 13-22
    conditions = [
        (hour >= 13) & (hour < 22),
        (hour >= 8) & (hour < 13),
        (hour < 8) | (hour >= 22)
    ]
    choices = ['NY', 'London', 'Asia']
    return np.select(conditions, choices, default='Asia')

def run_discovery():
    print("Preparing Full Edge V2 Dataset with Regime Classification...")
    df = prepare_dataset()
    if df is None: return
    
    df['session'] = calculate_session(df['time'])
    df_clean = df.dropna(subset=['sell_edge_score', 'market_regime', 'target_sell']).copy()
    
    # Tier A Filter
    df_edge = df_clean[df_clean['sell_edge_score'] >= 80]
    total_tier_a = len(df_edge)
    
    print(f"\n--- Regime Discovery Engine ---")
    print(f"Total Tier A Signals (Edge >= 80): {total_tier_a}")
    print("-" * 80)
    print(f"{'Regime':<15} | {'Trades':<8} | {'Win Rate':<10} | {'PF':<8} | {'Max DD':<8} | {'Expectancy'}")
    print("-" * 80)
    
    regimes = df_edge['market_regime'].unique()
    
    # Track for session breakdown
    session_stats = {}
    
    for regime in sorted(regimes):
        df_regime = df_edge[df_edge['market_regime'] == regime]
        trades = len(df_regime)
        if trades < 5: continue
        
        wins = df_regime['target_sell'].sum()
        losses = trades - wins
        win_rate = (wins / trades) * 100
        
        gross_profit = wins * 1.5
        gross_loss = losses * 1.0
        pf = gross_profit / gross_loss if gross_loss > 0 else 999.0
        
        expectancy = ((win_rate/100)*1.5) - ((1-(win_rate/100))*1.0)
        returns = pd.Series([1.5 if y == 1 else -1.0 for y in df_regime['target_sell']]) / 100.0
        dd = calculate_max_dd(returns)
        
        print(f"{regime:<15} | {trades:<8} | {win_rate:>6.1f}%    | {pf:>6.2f}   | {dd:>6.1f}% | {expectancy:>6.2f} R")
        
        # Calculate session specific
        session_stats[regime] = {}
        for session in ['London', 'NY', 'Asia']:
            df_sess = df_regime[df_regime['session'] == session]
            s_trades = len(df_sess)
            if s_trades < 5:
                session_stats[regime][session] = "N/A"
                continue
            s_wins = df_sess['target_sell'].sum()
            s_pf = (s_wins * 1.5) / ((s_trades - s_wins) * 1.0) if (s_trades - s_wins) > 0 else 999.0
            session_stats[regime][session] = f"PF {s_pf:.2f} ({s_trades}t)"

    print("\n--- Regime Performance Matrix (By Session) ---")
    print(f"{'Regime':<15} | {'London':<15} | {'NY':<15} | {'Asia':<15}")
    print("-" * 65)
    for regime in sorted(regimes):
        if regime in session_stats:
            lon = session_stats[regime].get('London', 'N/A')
            ny = session_stats[regime].get('NY', 'N/A')
            asia = session_stats[regime].get('Asia', 'N/A')
            print(f"{regime:<15} | {lon:<15} | {ny:<15} | {asia:<15}")

if __name__ == "__main__":
    run_discovery()
