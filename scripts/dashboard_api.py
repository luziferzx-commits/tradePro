from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pandas as pd
import json

app = FastAPI(title="GQOS Telemetry API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "trades.db"

def query_db(query: str, params=()) -> list:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(query, conn, params=params)
            return df.to_dict(orient="records")
    except Exception as e:
        print(f"DB Query Error: {e}")
        return []

@app.get("/api/summary")
def get_summary():
    # Signals
    signals_data = query_db("""
        SELECT 
            COUNT(*) as total_signals,
            SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) as accepted
        FROM trade_signals
    """)
    if not signals_data: return {}
    d = signals_data[0]
    total = d.get('total_signals', 0)
    accepted = d.get('accepted', 0)
    
    # Trades
    trades_data = query_db("""
        SELECT COUNT(*) as total_trades, SUM(profit) as total_profit
        FROM shadow_trades
        WHERE status = 'CLOSED'
    """)
    t = trades_data[0] if trades_data else {}
    
    return {
        "acceptance_pct": round(accepted * 100.0 / total, 2) if total > 0 else 0.0,
        "total_signals": total,
        "total_trades": t.get('total_trades', 0),
        "total_profit": t.get('total_profit', 0.0)
    }

@app.get("/api/recent_signals")
def get_recent_signals(limit: int = 50):
    return query_db("""
        SELECT timestamp, symbol, direction, conviction, threshold, decision
        FROM trade_signals
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))

@app.get("/api/open_positions")
def get_open_positions():
    return query_db("""
        SELECT ticket, symbol, direction, lot, entry_price, status, open_time
        FROM shadow_trades
        WHERE status = 'OPEN'
        ORDER BY open_time DESC
    """)

@app.get("/api/closed_trades")
def get_closed_trades(limit: int = 50):
    return query_db("""
        SELECT ticket, symbol, direction, lot, entry_price, profit, open_time, close_time
        FROM shadow_trades
        WHERE status = 'CLOSED'
        ORDER BY close_time DESC
        LIMIT ?
    """, (limit,))
