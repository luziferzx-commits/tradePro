import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from market.regime_detector import RegimeDetector
from market.session_detector import SessionDetector
from strategy.market_score import MarketScoreCalculator
from strategy.strategies.registry import StrategyRegistry
from strategy.strategies.ensemble_router import EnsembleRouter
from strategy.health_manager import StrategyHealthManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("ResearchBacktestV2")

def simulate_trade(records, start_idx, direction, entry_price, sl, tp):
    for j in range(start_idx + 1, len(records)):
        c = records[j]
        high = c['high']
        low = c['low']
        
        if direction == "BUY":
            if low <= sl: return -abs(entry_price - sl), "LOSS"
            if high >= tp: return abs(tp - entry_price), "WIN"
        elif direction == "SELL":
            if high >= sl: return -abs(sl - entry_price), "LOSS"
            if low <= tp: return abs(entry_price - tp), "WIN"
    return 0.0, "PENDING"

def generate_report(df_trades, report_path):
    logger.info("Generating multidimensional report...")
    if df_trades.empty:
        with open(report_path, 'w') as f:
            f.write("# Research Campaign v2\nNo trades executed.")
        return

    # Calculate basics per group
    def calc_metrics(g):
        wins = g[g['result'] == 'WIN']
        losses = g[g['result'] == 'LOSS']
        gross_profit = wins['pnl'].sum()
        gross_loss = abs(losses['pnl'].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else 99.0
        win_rate = len(wins) / len(g) * 100 if len(g) > 0 else 0
        
        # Max DD
        cum_pnl = g['pnl'].cumsum()
        peak = cum_pnl.cummax()
        dd = peak - cum_pnl
        max_dd = dd.max()
        
        r_mults = g.get('r_multiple', pd.Series([0]*len(g)))
        exp_r = r_mults.mean() if not r_mults.empty else 0.0
        avg_rr = r_mults[r_mults > 0].mean() if not r_mults[r_mults > 0].empty else 0.0

        return pd.Series({
            'Trades': len(g),
            'PF': pf,
            'Exp_R': exp_r,
            'WinRate': win_rate,
            'AvgRR': avg_rr,
            'MaxDD': max_dd
        })

    def format_table(df_agg):
        return df_agg.round(2).to_markdown()

    # 1. Engine Comparison
    engine_stats = df_trades.groupby('engine').apply(calc_metrics).reset_index()
    
    # Filter to ABC+Session for further dimensional analysis to find the edge
    df_abc_session = df_trades[df_trades['engine'] == 'ABC+Session'].copy()
    if df_abc_session.empty:
        df_abc_session = df_trades # fallback

    # 2. By Session
    session_stats = df_abc_session.groupby('session').apply(calc_metrics).reset_index()
    
    # 3. By Symbol
    symbol_stats = df_abc_session.groupby('symbol').apply(calc_metrics).reset_index()
    
    # 4. Symbol x Session PF
    sym_sess = pd.pivot_table(df_abc_session, values='pnl', index='symbol', columns='session', aggfunc=lambda x: x[x>0].sum() / abs(x[x<0].sum()) if abs(x[x<0].sum())>0 else 99)
    
    # 5. Strategy x Session PF
    strat_sess = pd.pivot_table(df_abc_session, values='pnl', index='strategy', columns='session', aggfunc=lambda x: x[x>0].sum() / abs(x[x<0].sum()) if abs(x[x<0].sum())>0 else 99)
    
    # 6. Regime x Session PF
    regime_sess = pd.pivot_table(df_abc_session, values='pnl', index='regime', columns='session', aggfunc=lambda x: x[x>0].sum() / abs(x[x<0].sum()) if abs(x[x<0].sum())>0 else 99)
    
    # 7. Hour
    hour_stats = df_abc_session.groupby('hour').apply(calc_metrics).reset_index()
    
    # 8. Weekday
    weekday_stats = df_abc_session.groupby('weekday').apply(calc_metrics).reset_index()

    # 9. Leaderboard (Symbol + Session + Strategy)
    df_abc_session['combo'] = df_abc_session['symbol'] + " | " + df_abc_session['session'] + " | " + df_abc_session['strategy']
    combo_stats = df_abc_session.groupby('combo').apply(calc_metrics).reset_index()
    
    # Filter out weak samples
    valid_combos = combo_stats[combo_stats['Trades'] >= 30].sort_values('PF', ascending=False)
    
    leaderboard = valid_combos.head(10)
    worstboard = valid_combos.tail(10).sort_values('PF', ascending=True)

    content = f"""# Research Campaign v2: Dimensional Edge Analysis

*Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
**RESEARCH_EXECUTION_MODEL = candle_close_fill**
*Note: This is a dimensional research simulation approximating execution at candle close. This is NOT a production-grade tick backtest. Profitability shown is for edge-discovery purposes only.*

## 1. Router Engine Benchmark
| Engine | Trades | PF | Exp R | Win Rate | Avg RR | Max DD |
|---|---|---|---|---|---|---|
"""
    for _, r in engine_stats.iterrows():
        content += f"| {r['engine']} | {r['Trades']:.0f} | {r['PF']:.2f} | {r['Exp_R']:.2f} | {r['WinRate']:.1f}% | {r['AvgRR']:.2f} | {r['MaxDD']:.2f} |\n"

    content += f"""
---
*The following dimensional analysis uses the `ABC+Session` engine.*

## 2. Performance by Session
{format_table(session_stats)}

## 3. Performance by Symbol
{format_table(symbol_stats)}

## 4. Session × Symbol (PF Matrix)
{sym_sess.round(2).to_markdown()}

## 5. Strategy × Session (PF Matrix)
{strat_sess.round(2).to_markdown()}

## 6. Regime × Session (PF Matrix)
{regime_sess.round(2).to_markdown()}

## 7. Performance by Hour (UTC)
{format_table(hour_stats)}

## 8. Performance by Weekday (0=Mon, 4=Fri)
{format_table(weekday_stats)}

---

## 9. Best Combinations Leaderboard (Min 30 Trades)
{format_table(leaderboard)}

## 10. Worst Combinations Leaderboard (Min 30 Trades)
{format_table(worstboard)}

"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)
    logger.info(f"Report saved to {report_path}")

def main():
    parser = argparse.ArgumentParser(description="Research Backtest V2")
    parser.add_argument("--candles", type=int, default=1000, help="Number of historical candles to fetch")
    parser.add_argument("--symbols", type=str, nargs='+', default=["XAUUSD"], help="List of symbols to backtest")
    args = parser.parse_args()

    if not mt5_client.connect():
        logger.error("Failed to connect to MT5.")
        return

    all_trades = []
    
    # Routers
    router_abc = EnsembleRouter(trading_cost_r=0.1, min_ev_threshold=0.05)
    router_abc_session = EnsembleRouter(trading_cost_r=0.1, min_ev_threshold=0.05)
    
    # We create a fresh health manager for the Health Replay
    # Force it to use a temporary state file so it doesn't corrupt production
    health_manager = StrategyHealthManager(state_file="config/research_temp_health.json")
    router_abc_health = EnsembleRouter(trading_cost_r=0.1, min_ev_threshold=0.05)
    router_abc_health.health_manager = health_manager
    
    session_detector = SessionDetector()

    for symbol in args.symbols:
        logger.info(f"Processing {symbol}...")
        df = mt5_client.get_historical_data(symbol, "M5", args.candles)
        if df.empty:
            logger.warning(f"No data for {symbol}, skipping.")
            continue
            
        logger.info("Calculating Indicators...")
        df = IndicatorCalculator.add_indicators(df)
        df['hour'] = pd.to_datetime(df['time']).dt.hour
        df['weekday'] = pd.to_datetime(df['time']).dt.weekday
        
        records = df.to_dict('records')
        registry = StrategyRegistry(symbol, "M5")
        
        logger.info("Simulating execution loop...")
        for i in range(50, len(records) - 1):
            c = records[i]
            
            # Simplified localized regime array to speed up
            regime = {
                "is_high_volatility": c.get('adx', 0) > 25,
                "is_ranging": c.get('adx', 0) < 25,
                "is_trending_up": c.get('ema50_slope', 0) > 0.5,
                "is_trending_down": c.get('ema50_slope', 0) < -0.5
            }
            
            sess_label = SessionDetector.detect(c['time'].timestamp())
            
            # --- 1. LEGACY ---
            # To speed up, we pass a small slice to MarketScoreCalculator
            short_slice = df.iloc[i-5:i+1]
            legacy_score = MarketScoreCalculator.calculate(short_slice, regime)
            if legacy_score['final_direction'] != "NEUTRAL":
                entry = c['close']
                atr = c.get('atr', 2.0)
                # Approximate SL/TP for legacy
                sl_dist = atr * 1.5
                sl = entry - sl_dist if legacy_score['final_direction'] == "BUY" else entry + sl_dist
                tp = entry + sl_dist*1.5 if legacy_score['final_direction'] == "BUY" else entry - sl_dist*1.5
                pnl, res = simulate_trade(records, i, legacy_score['final_direction'], entry, sl, tp)
                if res != "PENDING":
                    all_trades.append({
                        "engine": "Legacy", "symbol": symbol, "session": sess_label, "regime": "TREND" if regime['is_trending_up'] else "RANGE",
                        "strategy": legacy_score['setup_name'], "hour": c['hour'], "weekday": c['weekday'], 
                        "pnl": pnl, "result": res, "r_multiple": pnl / sl_dist if sl_dist > 0 else 0
                    })
                    
            # Generate ABC Signals
            # Instead of passing the whole slice which is slow, we use registry which internally uses latest row
            # For backtesting, we ideally call evaluate(slice) but `backtest_strategies_abc.py` passed `df_slice`
            # We will pass df.iloc[i-50:i+1]
            df_slice = df.iloc[i-50:i+1]
            
            # --- 2. ABC ---
            # Temporarily disable session routing
            os.environ["SESSION_AWARE_ROUTER"] = "false"
            sig_abc = router_abc.route(df_slice, regime, registry)
            if sig_abc.direction != "NEUTRAL":
                pnl, res = simulate_trade(records, i, sig_abc.direction, sig_abc.entry_price, sig_abc.stop_loss, sig_abc.take_profit)
                if res != "PENDING":
                    sl_dist = abs(sig_abc.entry_price - sig_abc.stop_loss)
                    all_trades.append({
                        "engine": "ABC", "symbol": symbol, "session": sess_label, "regime": "TREND" if regime['is_trending_up'] else "RANGE",
                        "strategy": sig_abc.strategy_id, "hour": c['hour'], "weekday": c['weekday'], 
                        "pnl": pnl, "result": res, "r_multiple": pnl / sl_dist if sl_dist > 0 else 0
                    })
            
            # --- 3. ABC+Session ---
            os.environ["SESSION_AWARE_ROUTER"] = "true"
            sig_sess = router_abc_session.route(df_slice, regime, registry, session_info={"session_label": sess_label})
            if sig_sess.direction != "NEUTRAL":
                pnl, res = simulate_trade(records, i, sig_sess.direction, sig_sess.entry_price, sig_sess.stop_loss, sig_sess.take_profit)
                if res != "PENDING":
                    sl_dist = abs(sig_sess.entry_price - sig_sess.stop_loss)
                    all_trades.append({
                        "engine": "ABC+Session", "symbol": symbol, "session": sess_label, "regime": "TREND" if regime['is_trending_up'] else "RANGE",
                        "strategy": sig_sess.strategy_id, "hour": c['hour'], "weekday": c['weekday'], 
                        "pnl": pnl, "result": res, "r_multiple": pnl / sl_dist if sl_dist > 0 else 0
                    })

            # --- 4. ABC+Session+Health ---
            os.environ["SESSION_AWARE_ROUTER"] = "true"
            sig_health = router_abc_health.route(df_slice, regime, registry, session_info={"session_label": sess_label})
            if sig_health.direction != "NEUTRAL":
                pnl, res = simulate_trade(records, i, sig_health.direction, sig_health.entry_price, sig_health.stop_loss, sig_health.take_profit)
                if res != "PENDING":
                    sl_dist = abs(sig_health.entry_price - sig_health.stop_loss)
                    r_mult = pnl / sl_dist if sl_dist > 0 else 0
                    all_trades.append({
                        "engine": "ABC+Session+Health", "symbol": symbol, "session": sess_label, "regime": "TREND" if regime['is_trending_up'] else "RANGE",
                        "strategy": sig_health.strategy_id, "hour": c['hour'], "weekday": c['weekday'], 
                        "pnl": pnl, "result": res, "r_multiple": r_mult
                    })
                    # Feedback loop!
                    strat_trades = [t for t in all_trades if t['engine'] == "ABC+Session+Health" and t['strategy'] == sig_health.strategy_id]
                    s_wins = [t for t in strat_trades if t['result'] == 'WIN']
                    pf = sum(t['pnl'] for t in s_wins) / abs(sum(t['pnl'] for t in strat_trades if t['result'] == 'LOSS')) if sum(t['pnl'] for t in strat_trades if t['result'] == 'LOSS') != 0 else 99.0
                    health_manager.update_metrics(
                        strategy_id=sig_health.strategy_id, pf=pf, expectancy=r_mult, 
                        win_rate=len(s_wins)/len(strat_trades), max_dd=0.02, avg_rr=1.5, trade_count=len(strat_trades)
                    )

    if not all_trades:
        logger.warning("No trades generated across all configurations.")
        return

    logger.info("Saving trade log...")
    df_trades = pd.DataFrame(all_trades)
    os.makedirs("results", exist_ok=True)
    df_trades.to_csv("results/research_backtest_v2_trades.csv", index=False)
    
    report_path = "reports/RESEARCH_CAMPAIGN_V2_REPORT.md"
    generate_report(df_trades, report_path)

if __name__ == '__main__':
    main()
