import MetaTrader5 as mt5
import pandas as pd
import json
import os
from execution.mt5_direction import closing_deal_position_direction

def init_mt5():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return False
    return True

def get_account_info():
    if not init_mt5(): return None
    acc = mt5.account_info()
    if not acc: return None
    return {
        "balance": acc.balance,
        "equity": acc.equity,
        "margin": acc.margin,
        "margin_free": acc.margin_free,
        "margin_level": acc.margin_level,
        "profit": acc.profit
    }

def get_open_positions():
    if not init_mt5(): return []
    pos = mt5.positions_get()
    if not pos: return []
    
    positions = []
    for p in pos:
        positions.append({
            "ticket": p.ticket,
            "symbol": p.symbol,
            "direction": "BUY" if p.type == 0 else "SELL",
            "volume": p.volume,
            "entry_price": p.price_open,
            "sl": p.sl,
            "tp": p.tp,
            "current_price": p.price_current,
            "profit": p.profit,
            "time": p.time
        })
    return positions

def get_ledger_stats(ledger_path="gqos_ledger_state.json"):
    try:
        with open(ledger_path, "r") as f:
            return json.load(f)
    except:
        return {}

def get_learning_progress(pending_path="data/learning/pending_trades.json"):
    try:
        with open(pending_path, "r") as f:
            data = json.load(f)
            return len(data)
    except:
        return 0

def get_pattern_db(db_path="data/pattern_store/pattern_database.parquet"):
    try:
        if os.path.exists(db_path):
            return pd.read_parquet(db_path)
    except Exception as e:
        print(f"Error loading Pattern DB: {e}")
    return pd.DataFrame()

def get_trade_history(days=1):
    if not init_mt5(): return []
    from datetime import datetime, timedelta
    
    today = datetime.now()
    start = today - timedelta(days=days)
    deals = mt5.history_deals_get(start, today)
    if not deals: return []
    
    history = []
    for d in deals:
        if d.entry == mt5.DEAL_ENTRY_OUT: # Only closing deals
            history.append({
                "ticket": d.ticket,
                "symbol": d.symbol,
                "direction": closing_deal_position_direction(d.type),
                "volume": d.volume,
                "price": d.price,
                "profit": d.profit,
                "time": d.time
            })
    return history
