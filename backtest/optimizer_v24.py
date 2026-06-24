import pandas as pd
import json
import itertools
from datetime import datetime
import os
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from market.regime_detector import RegimeDetector
from backtest.runner import BacktestRunner
from strategy.setups import SetupEvaluator
from config.settings import settings

def run_optimizer():
    if not mt5_client.connect():
        print("Failed to connect to MT5.")
        return
        
    df = mt5_client.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, 50000)
    if df is None or df.empty:
        print("No data fetched.")
        return
    
    print(f"Loaded {len(df)} candles.")
    df = IndicatorCalculator.add_indicators(df)
    
    print("Pre-calculating setups for all candles (this takes a few seconds)...")
    scores_list = []
    for i in range(200, len(df)):
        df_slice = df.iloc[i-5:i+1]
        regime_slice = df.iloc[i-50:i+1]
        regime = RegimeDetector.detect(regime_slice)
        setups = SetupEvaluator.evaluate_all(df_slice, regime)
        scores_list.append({"setups": setups, "regime": regime})

    # Baseline Parameters
    th = 60
    atr_mult = 2.0
    rr = 2.5
    target_setup = "Volatility Expansion Breakout"
    
    # ATR percentiles
    atr_series = df['atr'].dropna()
    atr_p20 = atr_series.quantile(0.20)
    atr_p90 = atr_series.quantile(0.90)
    atr_percentiles = {'p20': atr_p20, 'p90': atr_p90}

    # Filter Options
    regime_filters = ["ALL", "HIGH_VOLATILITY_ONLY", "TRENDING_UP_DOWN_AND_RISING_ADX"]
    session_filters = ["ALL", "NY_ONLY", "LONDON_ONLY", "LONDON_AND_NY"]
    cooldown_candles = [0, 3, 6, 12]
    atr_filters = ["ALL", "MID_ONLY"]
    direction_filters = ["BOTH", "BUY_ONLY", "SELL_ONLY"]
    
    records = df.to_dict('records')
    runner = BacktestRunner(spread_points=settings.BACKTEST_SPREAD_POINTS)
    
    def evaluate_combination(f_regime, f_session, f_cool, f_atr, f_dir):
        trades = runner.run(
            records, scores_list, th, atr_mult, rr, target_setup,
            filter_regime=f_regime, filter_session=f_session, cooldown_candles=f_cool, 
            filter_atr=f_atr, filter_direction=f_dir, atr_percentiles=atr_percentiles
        )
        
        trades_df = pd.DataFrame(trades)
        if trades_df.empty:
            return None, trades_df
            
        total_trades = len(trades_df)
        wins = len(trades_df[trades_df['result_r'] > 0])
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        avg_r = trades_df['result_r'].mean()
        std_r = trades_df['result_r'].std()
        sharpe = (avg_r / std_r) if std_r and std_r > 0 else 0
        
        trades_df['cumulative_r'] = trades_df['result_r'].cumsum()
        trades_df['peak'] = trades_df['cumulative_r'].cummax()
        trades_df['drawdown'] = trades_df['peak'] - trades_df['cumulative_r']
        max_dd_r = trades_df['drawdown'].max()
        
        gross_profit = trades_df[trades_df['result_r'] > 0]['result_r'].sum()
        gross_loss = abs(trades_df[trades_df['result_r'] < 0]['result_r'].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        res = {
            "regime": f_regime,
            "session": f_session,
            "cooldown": f_cool,
            "atr_filter": f_atr,
            "direction": f_dir,
            "total_trades": total_trades,
            "win_rate": round(win_rate * 100, 2),
            "profit_factor": round(pf, 3),
            "expectancy": round(avg_r, 3),
            "max_drawdown_r": round(max_dd_r, 2),
            "sharpe": round(sharpe, 3)
        }
        return res, trades_df

    print("\n--- 1. Single Filter Tests ---")
    single_tests = [
        ("BASELINE", "ALL", "ALL", 0, "ALL", "BOTH"),
        ("Regime: HIGH_VOL", "HIGH_VOLATILITY_ONLY", "ALL", 0, "ALL", "BOTH"),
        ("Regime: TREND_ADX", "TRENDING_UP_DOWN_AND_RISING_ADX", "ALL", 0, "ALL", "BOTH"),
        ("Session: NY_ONLY", "ALL", "NY_ONLY", 0, "ALL", "BOTH"),
        ("Session: LONDON_ONLY", "ALL", "LONDON_ONLY", 0, "ALL", "BOTH"),
        ("Session: LON_NY", "ALL", "LONDON_AND_NY", 0, "ALL", "BOTH"),
        ("Cooldown: 3", "ALL", "ALL", 3, "ALL", "BOTH"),
        ("Cooldown: 6", "ALL", "ALL", 6, "ALL", "BOTH"),
        ("Cooldown: 12", "ALL", "ALL", 12, "ALL", "BOTH"),
        ("ATR: MID_ONLY", "ALL", "ALL", 0, "MID_ONLY", "BOTH"),
        ("Dir: BUY_ONLY", "ALL", "ALL", 0, "ALL", "BUY_ONLY"),
        ("Dir: SELL_ONLY", "ALL", "ALL", 0, "ALL", "SELL_ONLY"),
    ]
    
    for name, fr, fs, fc, fa, fd in single_tests:
        res, _ = evaluate_combination(fr, fs, fc, fa, fd)
        if res:
            print(f"{name:<20} | Trades: {res['total_trades']:<4} | PF: {res['profit_factor']:<5} | MaxDD: {res['max_drawdown_r']:<5}")

    print("\n--- 2. Grid Search Combinations ---")
    combinations = list(itertools.product(regime_filters, session_filters, cooldown_candles, atr_filters, direction_filters))
    total_combs = len(combinations)
    
    results = []
    candidates = []
    
    for idx, (fr, fs, fc, fa, fd) in enumerate(combinations):
        if idx % 50 == 0:
            print(f"Progress: {idx}/{total_combs}")
            
        res, trades_df = evaluate_combination(fr, fs, fc, fa, fd)
        if res:
            results.append(res)
            
            # Check candidate criteria: Trades > 200, PF > 1.3, Max DD < 15
            if res['total_trades'] >= 200 and res['profit_factor'] > 1.3 and res['max_drawdown_r'] < 15:
                
                # Calculate monthly breakdown
                trades_df['datetime'] = pd.to_datetime(trades_df['timestamp'])
                trades_df['month'] = trades_df['datetime'].dt.to_period('M').astype(str)
                
                monthly = []
                for m, grp in trades_df.groupby('month'):
                    m_trades = len(grp)
                    m_wins = len(grp[grp['result_r'] > 0])
                    m_r = round(grp['result_r'].sum(), 2)
                    
                    grp['cum_r'] = grp['result_r'].cumsum()
                    m_peak = grp['cum_r'].cummax()
                    m_dd = round((m_peak - grp['cum_r']).max(), 2)
                    
                    monthly.append({
                        "month": str(m),
                        "trades": m_trades,
                        "win_rate": round(m_wins / m_trades * 100, 2) if m_trades > 0 else 0,
                        "net_r": m_r,
                        "max_dd_r": m_dd
                    })
                    
                res['monthly_breakdown'] = monthly
                candidates.append(res)
                
    results_df = pd.DataFrame(results)
    today = datetime.now().strftime("%Y-%m-%d")
    
    reports_dir = "backtest/reports"
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
        
    results_df.to_csv(f"{reports_dir}/volatility_expansion_filters_{today}.csv", index=False)
    
    with open(f"{reports_dir}/v24_best_candidates.json", "w") as f:
        json.dump(candidates, f, indent=4)
        
    print(f"\nFound {len(candidates)} candidates matching criteria (Trades>200, PF>1.3, MaxDD<15R)!")
    for c in candidates:
        print(f"\nCandidate: Reg={c['regime']} Ses={c['session']} Cool={c['cooldown']} ATR={c['atr_filter']} Dir={c['direction']}")
        print(f"Trades: {c['total_trades']} | PF: {c['profit_factor']} | MaxDD: {c['max_drawdown_r']}R | Expectancy: {c['expectancy']}R")
        print("Monthly Breakdown:")
        for m in c['monthly_breakdown']:
            print(f"  {m['month']}: {m['trades']} trades, {m['net_r']}R, DD {m['max_dd_r']}R")

if __name__ == "__main__":
    run_optimizer()
