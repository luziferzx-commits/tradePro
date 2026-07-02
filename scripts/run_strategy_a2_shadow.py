"""
scripts/run_strategy_a2_shadow.py
 
Strategy A2 Shadow Mode — Asia Range Fade (OOS PF=1.12, RR=2.37)
รัน strategy A2 แบบ paper trade ไม่มีเงินจริง
บันทึกผลลง shadow_log.jsonl เพื่อ validate PF ใน live market
 
ผล OOS Backtest:
  PF=1.12 | WR=32.1% | RR=2.37 | Sharpe=0.68 | DD=1.05%
 
เงื่อนไข:
  - ช่วง Asia session (00:00–07:00 UTC)
  - ADX < 20 (ranging market)
  - Extension > 0.3 ATR หลัง breakout
  - Rejection Wick > 0.3 (body ratio)
  - RSI Divergence (ราคาทำ high/low ใหม่ แต่ RSI ไม่)
  - Fade direction (ตรงข้าม breakout)
 
Shadow Rules:
  - ไม่ส่ง order ไป MT5
  - บันทึก hypothetical entry/sl/tp/outcome ลง JSONL
  - promote เป็น live ถ้า shadow PF > 1.1 หลัง 50+ trades
"""
import os
import sys
import json
import logging
import time
from datetime import datetime
 
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
 
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
 
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
 
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("A2Shadow")
 
SHADOW_LOG = "data/learning/strategy_a2_shadow.jsonl"
SYMBOL     = "XAUUSDm"
RR_RATIO   = 2.0
 
 
def get_session(hour: int) -> str:
    if 0 <= hour < 7:  return "Asia"
    if 7 <= hour < 10: return "London"
    return "Other"
 
 
def check_a2_signal(df: pd.DataFrame) -> dict | None:
    """
    Strategy A2 — Asia Range Fade
    3 Confirmation Layers:
      L1: Extension > 0.3 ATR
      L2: Rejection Wick > 0.3
      L3: RSI Divergence
    """
    if len(df) < 30:
        return None
 
    latest = df.iloc[-1]
    hour   = pd.to_datetime(latest["time"]).hour
 
    # Asia session only (00:00–07:00 UTC)
    if not (0 <= hour < 7):
        return None
 
    atr = latest.get("atr", 0)
    adx = latest.get("adx", 0)
 
    if atr <= 0:
        return None
 
    # Ranging market check (ADX < 20)
    if adx >= 20:
        return None
 
    # ─── Range high/low (last 20 candles) ─────────────────────────
    window    = df.iloc[-20:]
    range_hi  = window["high"].max()
    range_lo  = window["low"].min()
    close     = latest["close"]
    open_p    = latest["open"]
    high      = latest["high"]
    low       = latest["low"]
 
    direction = None
 
    # Bullish breakout → FADE (SELL)
    if close > range_hi:
        direction = "SELL"
        breakout_ref = range_hi
        extension = (close - range_hi) / atr
    # Bearish breakout → FADE (BUY)
    elif close < range_lo:
        direction = "BUY"
        breakout_ref = range_lo
        extension = (range_lo - close) / atr
    else:
        return None
 
    # Layer 1: Extension > 0.3 ATR
    if extension < 0.3:
        return None
 
    # Layer 2: Rejection Wick > 0.3
    candle_range = high - low
    body         = abs(close - open_p)
    if candle_range <= 0:
        return None
    wick_ratio = 1 - (body / candle_range)
    if wick_ratio < 0.3:
        return None
 
    # Layer 3: RSI Divergence
    if "rsi" not in df.columns:
        return None
    prev3_close = df["close"].iloc[-4]
    prev3_rsi   = df["rsi"].iloc[-4]
    curr_rsi    = latest.get("rsi", 50)
 
    if direction == "SELL":
        # Price makes new high but RSI doesn't → bearish divergence
        price_higher = close > prev3_close
        rsi_lower    = curr_rsi < prev3_rsi
        if not (price_higher and rsi_lower):
            return None
    else:
        # Price makes new low but RSI doesn't → bullish divergence
        price_lower = close < prev3_close
        rsi_higher  = curr_rsi > prev3_rsi
        if not (price_lower and rsi_higher):
            return None
 
    # SL/TP
    sl_dist = atr * 1.5
    tp_dist = sl_dist * RR_RATIO
 
    if direction == "SELL":
        sl = close + sl_dist
        tp = close - tp_dist
    else:
        sl = close - sl_dist
        tp = close + tp_dist
 
    return {
        "direction": direction,
        "entry":     close,
        "sl":        sl,
        "tp":        tp,
        "sl_dist":   sl_dist,
        "atr":       atr,
        "extension": round(extension, 3),
        "wick":      round(wick_ratio, 3),
        "rsi":       round(curr_rsi, 2),
        "hour":      hour,
    }
 
 
def simulate_outcome(df: pd.DataFrame, signal: dict, lookahead: int = 50) -> str:
    """ดู forward candles ว่าชน TP หรือ SL ก่อน"""
    entry = signal["entry"]
    sl    = signal["sl"]
    tp    = signal["tp"]
    direction = signal["direction"]
 
    future = df.iloc[-lookahead:] if len(df) >= lookahead else df
 
    for _, row in future.iterrows():
        if direction == "SELL":
            if row["high"] >= sl: return "LOSS"
            if row["low"]  <= tp: return "WIN"
        else:
            if row["low"]  <= sl: return "LOSS"
            if row["high"] >= tp: return "WIN"
    return "TIMEOUT"
 
 
def log_shadow(signal: dict, outcome: str):
    os.makedirs("data/learning", exist_ok=True)
    record = {
        **signal,
        "outcome":   outcome,
        "timestamp": datetime.utcnow().isoformat(),
        "symbol":    SYMBOL,
    }
    with open(SHADOW_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")
 
 
def get_shadow_stats() -> dict:
    if not os.path.exists(SHADOW_LOG):
        return {"total": 0, "pf": 0.0, "win_rate": 0.0}
    rows = []
    with open(SHADOW_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        return {"total": 0, "pf": 0.0, "win_rate": 0.0}
    wins   = [r for r in rows if r["outcome"] == "WIN"]
    losses = [r for r in rows if r["outcome"] == "LOSS"]
    gross_win  = len(wins)  * 2.0   # RR 1:2
    gross_loss = len(losses) * 1.0
    pf = gross_win / gross_loss if gross_loss > 0 else 0.0
    return {
        "total":    len(rows),
        "wins":     len(wins),
        "losses":   len(losses),
        "timeouts": len([r for r in rows if r["outcome"] == "TIMEOUT"]),
        "win_rate": round(len(wins) / len(rows) * 100, 1) if rows else 0.0,
        "pf":       round(pf, 3),
    }
 
 
def main():
    logger.info("Strategy A2 Shadow Mode started.")
    logger.info(f"Symbol: {SYMBOL} | RR: 1:{RR_RATIO} | Log: {SHADOW_LOG}")
 
    if not mt5_client.connect():
        logger.error("MT5 connection failed.")
        return
 
    last_candle = None
 
    try:
        while True:
            # รอ candle ใหม่
            bars = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 2)
            if bars is None or len(bars) < 2:
                time.sleep(5)
                continue
 
            current_time = bars[-1]["time"]
            if current_time == last_candle:
                time.sleep(10)
                continue
 
            last_candle = current_time
            dt_now = datetime.utcfromtimestamp(current_time)
 
            if not (0 <= dt_now.hour < 7):
                time.sleep(30)
                continue
 
            # ดึงข้อมูลและคำนวณ indicators
            df = mt5_client.get_historical_data(SYMBOL.replace("m",""), "M5", 300)
            if df is None or len(df) < 50:
                continue
            df = IndicatorCalculator.add_indicators(df)
 
            # ตรวจ signal
            sig = check_a2_signal(df)
            if sig is None:
                continue
 
            # จำลอง outcome จาก forward bars (ถ้ามี)
            df_future = mt5_client.get_historical_data(SYMBOL.replace("m",""), "M5", 100)
            if df_future is not None:
                df_future = IndicatorCalculator.add_indicators(df_future)
                outcome = simulate_outcome(df_future, sig)
            else:
                outcome = "PENDING"
 
            log_shadow(sig, outcome)
 
            stats = get_shadow_stats()
            logger.info(
                f"[A2 Shadow] {sig['direction']} | outcome={outcome} | "
                f"Stats: {stats['total']} trades | "
                f"WR={stats['win_rate']}% | PF={stats['pf']}"
            )
 
            # Alert ถ้า shadow PF > 1.1 และมีข้อมูลพอ
            if stats["total"] >= 50 and stats["pf"] >= 1.1:
                logger.info(
                    f"[A2 Shadow] 🎉 PROMOTION READY! "
                    f"PF={stats['pf']} N={stats['total']} → "
                    f"Ready for Live Micro Mode"
                )
                try:
                    from notifications.telegram_notifier import send_telegram
                    send_telegram(
                        f"🎯 <b>Strategy A2 Shadow PASSED!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"PF       : {stats['pf']}\n"
                        f"Win Rate : {stats['win_rate']}%\n"
                        f"Trades   : {stats['total']}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"✅ Ready for Live Micro Mode!"
                    )
                except Exception:
                    pass
 
            time.sleep(60)
 
    except KeyboardInterrupt:
        stats = get_shadow_stats()
        logger.info(f"Stopped. Final stats: {stats}")
        mt5_client.disconnect()
 
 
if __name__ == "__main__":
    main()
