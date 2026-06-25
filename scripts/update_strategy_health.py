import os
import sys
import sqlite3
import pandas as pd
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from strategy.health_manager import StrategyHealthManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealthUpdater")

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'trades.db')

def fetch_strategy_metrics(strategy_id: str) -> dict:
    """
    Fetch the last 30 days of trades from SQLite and calculate metrics.
    If the table or data doesn't exist (e.g. during fresh setup), returns a simulated baseline.
    """
    if not os.path.exists(DB_PATH):
        logger.warning(f"DB not found at {DB_PATH}, returning empty metrics")
        return {"pf": 0.0, "expectancy": 0.0, "win_rate": 0.0, "max_dd": 0.0, "avg_rr": 0.0, "trade_count": 0}
        
    try:
        conn = sqlite3.connect(DB_PATH)
        # Assuming table `trades` and columns: strategy, pnl, r_multiple, status, timestamp
        query = f"SELECT * FROM trades WHERE strategy = '{strategy_id}' AND status IN ('CLOSED', 'SHADOW') ORDER BY timestamp DESC LIMIT 1000"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {"pf": 0.0, "expectancy": 0.0, "win_rate": 0.0, "max_dd": 0.0, "avg_rr": 0.0, "trade_count": 0}
            
        # Calculate PF
        gross_profit = df[df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else 99.0
        
        # Calculate Win Rate
        wins = len(df[df['pnl'] > 0])
        trade_count = len(df)
        win_rate = wins / trade_count if trade_count > 0 else 0.0
        
        # Calculate Expectancy R
        # Assume r_multiple exists
        if 'r_multiple' in df.columns:
            expectancy = df['r_multiple'].mean()
            avg_rr = df[df['r_multiple'] > 0]['r_multiple'].mean()
        else:
            expectancy = 0.0
            avg_rr = 0.0
            
        # Max DD calculation (simplified rolling sum)
        df['cum_pnl'] = df['pnl'].cumsum()
        df['peak'] = df['cum_pnl'].cummax()
        df['dd'] = df['peak'] - df['cum_pnl']
        # normalize to account percent (dummy math for now)
        max_dd = (df['dd'].max() / 100000.0) if not df['dd'].empty else 0.0
        
        return {
            "pf": pf,
            "expectancy": expectancy,
            "win_rate": win_rate,
            "max_dd": max_dd,
            "avg_rr": avg_rr,
            "trade_count": trade_count
        }
        
    except Exception as e:
        logger.warning(f"Failed to query DB: {e}. Defaulting to zeroes.")
        return {"pf": 0.0, "expectancy": 0.0, "win_rate": 0.0, "max_dd": 0.0, "avg_rr": 0.0, "trade_count": 0}

def rebuild_health():
    logger.info("Rebuilding Strategy Health from SQLite trades.db...")
    manager = StrategyHealthManager()
    
    # We rebuild for all known ABC strategies
    strategies = ["StrategyABreakout", "StrategyBTrendPullback", "StrategyCMeanReversion"]
    
    for strat in strategies:
        metrics = fetch_strategy_metrics(strat)
        manager.update_metrics(
            strategy_id=strat,
            pf=metrics["pf"],
            expectancy=metrics["expectancy"],
            win_rate=metrics["win_rate"],
            max_dd=metrics["max_dd"],
            avg_rr=metrics["avg_rr"],
            trade_count=metrics["trade_count"]
        )
        logger.info(f"Updated {strat}: PF={metrics['pf']:.2f}, Score={manager.get_state(strat).health_score:.1f}, Status={manager.get_state(strat).status}")
        
    manager.save_state()
    logger.info("Health states persisted to JSON.")

if __name__ == '__main__':
    rebuild_health()
