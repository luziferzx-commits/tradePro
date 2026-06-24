import requests
import logging

logger = logging.getLogger("GoldBot.Telegram")

TELEGRAM_BOT_TOKEN = "8698453701:AAEJ8D3mBVVL76dGjP4OltQCSgQUZARa3tE"
TELEGRAM_CHAT_ID = "1622021286"

def send_telegram(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")

def notify_trade_executed(direction, lot, entry, sl, tp, ticket, probability):
    emoji = "🟢" if direction == "BUY" else "🔴"
    msg = (
        f"{emoji} <b>TRADE EXECUTED</b>\n"
        f"─────────────────\n"
        f"Direction : {direction}\n"
        f"Lot       : {lot}\n"
        f"Entry     : {entry}\n"
        f"SL        : {sl}\n"
        f"TP        : {tp}\n"
        f"Ticket    : #{ticket}\n"
        f"ML Prob   : {probability:.3f}\n"
        f"─────────────────\n"
        f"⏳ Waiting for result..."
    )
    send_telegram(msg)

def notify_trade_closed(ticket, direction, profit, rr):
    emoji = "✅" if profit > 0 else "❌"
    msg = (
        f"{emoji} <b>TRADE CLOSED</b>\n"
        f"─────────────────\n"
        f"Ticket  : #{ticket}\n"
        f"Direction: {direction}\n"
        f"Profit  : {profit:.2f} USD\n"
        f"R:R     : {rr:.2f}\n"
        f"─────────────────"
    )
    send_telegram(msg)

def notify_bot_started():
    send_telegram(
        "🤖 <b>GoldBot Started</b>\n"
        "Market Memory ✅\n"
        "MT5 Connected ✅\n"
        "Watching for setup..."
    )

def notify_trade_rejected(reason, probability):
    pass  # Silent — do NOT notify on every rejection (too noisy)
