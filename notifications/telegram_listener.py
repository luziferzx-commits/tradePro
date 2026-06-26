import time
import threading
import requests
import logging
import MetaTrader5 as mt5
import pandas as pd
import json
from datetime import datetime
import os

from notifications.telegram_notifier import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, send_telegram

logger = logging.getLogger("GoldBot.TelegramListener")

class TelegramCommandListener:
    def __init__(self, alpha_worker, shutdown_callback=None):
        self.alpha_worker = alpha_worker
        self.shutdown_callback = shutdown_callback
        self.running = False
        self.last_update_id = 0
        self.base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
        self.known_tickets = set()

    def start(self):
        self.running = True
        threading.Thread(target=self._poll_updates, daemon=True).start()
        logger.info("TelegramCommandListener started.")

    def stop(self):
        self.running = False

    def _poll_updates(self):
        while self.running:
            try:
                url = f"{self.base_url}/getUpdates?offset={self.last_update_id + 1}&timeout=5"
                resp = requests.get(url, timeout=10)
                data = resp.json()

                if data.get("ok"):
                    for result in data.get("result", []):
                        self.last_update_id = result["update_id"]
                        msg = result.get("message", {})
                        text = msg.get("text", "")
                        
                        # Only accept commands from our chat id for security
                        if str(msg.get("chat", {}).get("id")) != str(TELEGRAM_CHAT_ID):
                            continue
                            
                        if text.startswith("/"):
                            self._handle_command(text.strip().lower())
            except Exception as e:
                # Suppress timeout errors
                pass
            
            self._check_closed_positions()
            time.sleep(1)

    def _check_closed_positions(self):
        try:
            pos = mt5.positions_get()
            current_tickets = set(p.ticket for p in pos) if pos else set()
            
            # Check for missing tickets (Closed)
            closed_tickets = self.known_tickets - current_tickets
            if closed_tickets:
                from notifications.telegram_notifier import notify_trade_closed
                for t in closed_tickets:
                    deals = mt5.history_deals_get(position=t)
                    if deals:
                        close_deal = deals[-1]
                        if close_deal.entry == mt5.DEAL_ENTRY_OUT:
                            profit = close_deal.profit
                            symbol = close_deal.symbol
                            # If it was a SELL deal to close, original was BUY
                            direction = "BUY" if close_deal.type == mt5.DEAL_TYPE_SELL else "SELL"
                            notify_trade_closed(t, symbol, direction, profit, 0.0)
            
            self.known_tickets = current_tickets
        except Exception as e:
            logger.error(f"Error checking closed positions: {e}")

    def _handle_command(self, cmd_text):
        if cmd_text == "/status":
            self._cmd_status()
        elif cmd_text == "/positions":
            self._cmd_positions()
        elif cmd_text == "/pause":
            self._cmd_pause()
        elif cmd_text == "/resume":
            self._cmd_resume()
        elif cmd_text == "/stop":
            self._cmd_stop()
        elif cmd_text == "/stats":
            self._cmd_stats()
        elif cmd_text == "/report":
            self._cmd_report()
        elif cmd_text == "/risk":
            self._cmd_risk()
        elif cmd_text == "/top":
            self._cmd_top()
        else:
            send_telegram("❌ Unknown command.\nAvailable: /status, /positions, /pause, /resume, /stop, /stats, /report, /risk, /top")

    def _cmd_status(self):
        acc = mt5.account_info()
        pos = mt5.positions_get() or []
        state = "PAUSED ⏸️" if getattr(self.alpha_worker, 'is_paused', False) else "RUNNING ▶️"
        
        msg = f"📊 <b>BOT STATUS</b>\n"
        msg += f"State: {state}\n"
        if acc:
            msg += f"Balance: {acc.balance:.2f}\n"
            msg += f"Equity: {acc.equity:.2f}\n"
            msg += f"Free Margin: {acc.margin_free:.2f}\n"
        msg += f"Open Positions: {len(pos)}"
        send_telegram(msg)

    def _cmd_positions(self):
        pos = mt5.positions_get() or []
        if not pos:
            send_telegram("0️⃣ No open positions.")
            return
            
        msg = f"📋 <b>OPEN POSITIONS ({len(pos)})</b>\n"
        for p in pos:
            direction = "BUY 🟢" if p.type == 0 else "SELL 🔴"
            msg += f"• <b>{p.symbol}</b> {direction} | Vol: {p.volume}\n"
            msg += f"  Entry: {p.price_open:.5f} | PnL: {p.profit:.2f}\n"
        send_telegram(msg)

    def _cmd_pause(self):
        self.alpha_worker.is_paused = True
        send_telegram("⏸️ <b>Bot PAUSED</b>\nNo new trades will be opened. Existing trades are still managed.")

    def _cmd_resume(self):
        self.alpha_worker.is_paused = False
        send_telegram("▶️ <b>Bot RESUMED</b>\nScanning for new trades...")

    def _cmd_stop(self):
        send_telegram("🚨 <b>EMERGENCY STOP TRIGGERED</b>\nClosing all positions and shutting down bot...")
        self.alpha_worker.is_paused = True
        
        # Close all positions
        pos = mt5.positions_get() or []
        closed_count = 0
        for p in pos:
            # Send market close order
            tick = mt5.symbol_info_tick(p.symbol)
            if not tick: continue
            
            close_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
            close_price = tick.bid if p.type == 0 else tick.ask
            
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": close_type,
                "position": p.ticket,
                "price": close_price,
                "deviation": 20,
                "magic": 999,
                "comment": "Emergency Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                closed_count += 1

        send_telegram(f"🛑 <b>BOT STOPPED</b>\nClosed {closed_count}/{len(pos)} positions. Shutting down system.")
        if self.shutdown_callback:
            self.shutdown_callback()

    def _cmd_stats(self):
        total_pnl = 0.0
        try:
            with open("gqos_ledger_state.json", "r") as f:
                data = json.load(f)
                realized = data.get("realized_pnl", 0.0)
                total_pnl = realized
        except:
            pass

        pending_count = 0
        try:
            with open("data/learning/pending_trades.json", "r") as f:
                pending_count = len(json.load(f))
        except:
            pass

        msg = f"📈 <b>STATISTICS</b>\n"
        msg += f"Total Ledger PnL: {total_pnl:.2f}\n"
        msg += f"Retrain Progress: {pending_count} pending / 50 trigger\n"
        send_telegram(msg)

    def _cmd_report(self):
        now = datetime.now()
        start_of_day = datetime(now.year, now.month, now.day)
        
        # ดึงประวัติการเทรดของวันนี้จาก MT5
        deals = mt5.history_deals_get(start_of_day, now)
        daily_pnl = 0.0
        trades_count = 0
        win_count = 0
        
        if deals:
            for deal in deals:
                # นับเฉพาะดีลขาออก (ปิดออเดอร์)
                if deal.entry == mt5.DEAL_ENTRY_OUT:
                    daily_pnl += deal.profit
                    trades_count += 1
                    if deal.profit > 0:
                        win_count += 1
                        
        win_rate = (win_count / trades_count * 100) if trades_count > 0 else 0.0
        
        acc = mt5.account_info()
        balance = acc.balance if acc else 0.0
        
        msg = f"📝 <b>DAILY REPORT ({start_of_day.strftime('%Y-%m-%d')})</b>\n"
        msg += f"─────────────────\n"
        msg += f"💰 Daily PnL : <b>{daily_pnl:+.2f} USD</b>\n"
        msg += f"📊 Total Trades : {trades_count}\n"
        msg += f"🏆 Win Rate   : {win_rate:.1f}%\n"
        msg += f"💵 Balance    : {balance:.2f} USD\n"
        msg += f"─────────────────"
        send_telegram(msg)

    def _cmd_risk(self):
        acc = mt5.account_info()
        if acc:
            margin_level = acc.margin_level if acc.margin_level else 0.0
            msg = f"🛡️ <b>RISK DASHBOARD</b>\n"
            msg += f"Margin Used: {acc.margin:.2f}\n"
            msg += f"Margin Free: {acc.margin_free:.2f}\n"
            msg += f"Margin Level: {margin_level:.2f}%\n"
            send_telegram(msg)
        else:
            send_telegram("❌ MT5 disconnected.")

    def _cmd_top(self):
        db_path = "data/pattern_store/pattern_database.parquet"
        if not os.path.exists(db_path):
            send_telegram("❌ Pattern DB not found.")
            return
            
        try:
            df = pd.read_parquet(db_path)
            # Filter valid sample size and sort
            df_filtered = df[df['sample_size'] >= 50]
            df_sorted = df_filtered.sort_values("aggregate_pf", ascending=False).head(5)
            msg = f"🏆 <b>TOP 5 PATTERNS</b>\n"
            for _, row in df_sorted.iterrows():
                msg += f"• ID:{row['pattern_id'][:6]} | PF:{row['aggregate_pf']:.2f} | N:{row['sample_size']}\n"
            send_telegram(msg)
        except Exception as e:
            send_telegram(f"❌ Error reading DB: {e}")
