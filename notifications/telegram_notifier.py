import requests
import logging
from datetime import datetime
 
logger = logging.getLogger("GoldBot.Telegram")
 
# Credentials loaded from environment (ไม่ hardcode ใน code)
import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")


def _clean_direction(direction) -> str:
    text = getattr(direction, "name", direction)
    text = str(text or "UNKNOWN").upper()
    if "BUY" in text or "LONG" in text:
        return "BUY"
    if "SELL" in text or "SHORT" in text:
        return "SELL"
    return "UNKNOWN"
 
def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing in .env")
        return False
    try:
        url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        return True
    except Exception as e:
        body = ""
        try:
            body = f" body={resp.text[:300]}"
        except Exception:
            pass
        logger.warning(f"Telegram notification failed: {e}{body}")
        return False
 
def notify_trade_executed(symbol, direction, lot, entry, sl, tp, ticket, probability=0.0):
    direction = _clean_direction(direction)
    emoji = "🟢" if direction == "BUY" else "🔴"
    prob_text = f"ML Prob   : {probability:.3f}\n" if probability > 0 else ""
    msg = (
        f"{emoji} <b>TRADE OPENED</b>\n"
        f"─────────────────\n"
        f"Symbol    : <b>{symbol}</b>\n"
        f"Direction : {direction}\n"
        f"Lot       : {lot}\n"
        f"Entry     : {entry}\n"
        f"SL        : {sl}\n"
        f"TP        : {tp}\n"
        f"Ticket    : #{ticket}\n"
        f"{prob_text}"
        f"─────────────────\n"
        f"⏳ Managing position..."
    )
    return send_telegram(msg)
 
def notify_trade_closed(ticket, symbol, direction, profit, rr=None, balance=0.0, duration_seconds=None):
    direction = _clean_direction(direction)
    
    if duration_seconds is not None and duration_seconds < 60 and profit < 0:
        emoji = "⚡"
        title = "<b>INSTANT CUT LOSS</b>"
    else:
        emoji = "✅" if profit > 0 else "❌"
        title = "<b>TRADE CLOSED</b>"
        
    balance_text = f"\nBalance : {balance:.2f} USD" if balance > 0 else ""
    try:
        rr_text = f"{float(rr):+.2f}R" if rr is not None else "N/A"
    except Exception:
        rr_text = "N/A"
    msg = (
        f"{emoji} {title}\n"
        f"─────────────────\n"
        f"Symbol   : <b>{symbol}</b>\n"
        f"Ticket   : #{ticket}\n"
        f"Direction: {direction}\n"
        f"Profit   : {profit:.2f} USD\n"
        f"R        : {rr_text}{balance_text}\n"
        f"─────────────────"
    )
    return send_telegram(msg)
 
def notify_bot_started():
    return send_telegram(
        "🤖 <b>GQOS Live Engine Started</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Market Memory      ✅\n"
        "MT5 Connected      ✅\n"
        "Learning Loop      ✅\n"
        "Dynamic Position   ✅\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎯 Watching for setups..."
    )
 
def notify_trade_rejected(reason, probability):
    pass  # Silent
 
# ─────────────────────────────────────────────────────────────
# ✅ ใหม่: Daily Report
# ─────────────────────────────────────────────────────────────
def notify_daily_report(
    balance: float,
    equity: float,
    daily_pnl: float,
    total_trades: int,
    wins: int,
    losses: int,
    best_trade: float,
    worst_trade: float,
    live_trades_total: int,
    retrain_progress: int,
    retrain_threshold: int,
    session_stats: dict,
):
    date_str  = datetime.utcnow().strftime("%Y-%m-%d")
    wr        = round(wins / total_trades * 100, 1) if total_trades > 0 else 0.0
    pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
    pnl_sign  = "+" if daily_pnl >= 0 else ""
 
    # Session breakdown
    session_lines = ""
    for sess, s in session_stats.items():
        if s["n"] > 0:
            session_lines += (
                f"  {sess:<12} {s['wins']}W {s['losses']}L "
                f"({s['win_rate']:.0f}%)\n"
            )
 
    msg = (
        f"📊 <b>GQOS Daily Report — {date_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance  : <b>${balance:.2f}</b>\n"
        f"📐 Equity   : ${equity:.2f}\n"
        f"{pnl_emoji} Daily PnL : <b>{pnl_sign}{daily_pnl:.2f} USD</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 Trades   : {total_trades} ({wins}W {losses}L)\n"
        f"🎯 Win Rate : {wr}%\n"
        f"🏆 Best     : +{best_trade:.2f} USD\n"
        f"💔 Worst    : {worst_trade:.2f} USD\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
 
    if session_lines:
        msg += f"🕐 Sessions:\n{session_lines}"
        msg += "━━━━━━━━━━━━━━━━━━\n"
 
    msg += (
        f"🧠 Learning : {live_trades_total} live trades\n"
        f"🔄 Retrain  : {retrain_progress}/{retrain_threshold} → next retrain\n"
    )
 
    send_telegram(msg)
