import time
import threading
import requests
import logging
import MetaTrader5 as mt5
import pandas as pd
import json
from datetime import datetime
import os
import html

from config.settings import settings
from execution.mt5_direction import closing_deal_position_direction
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
        self.poll_closed_positions = os.getenv("TELEGRAM_POLL_CLOSED_POSITIONS", "False").lower() in (
            "1",
            "true",
            "yes",
        )

    def start(self):
        self._refresh_known_tickets()
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
            except requests.exceptions.Timeout:
                pass
            except Exception as e:
                logger.warning(f"Telegram polling failed: {e}")
            
            if self.poll_closed_positions:
                self._check_closed_positions()
            time.sleep(1)

    def _refresh_known_tickets(self):
        try:
            pos = mt5.positions_get() or []
            self.known_tickets = {
                p.ticket
                for p in pos
                if getattr(p, "magic", settings.MAGIC_NUMBER) == settings.MAGIC_NUMBER
            }
        except Exception as e:
            logger.warning(f"Could not initialize known MT5 tickets for Telegram listener: {e}")
            self.known_tickets = set()

    def _check_closed_positions(self):
        try:
            pos = mt5.positions_get() or []
            current_tickets = {
                p.ticket
                for p in pos
                if getattr(p, "magic", settings.MAGIC_NUMBER) == settings.MAGIC_NUMBER
            }
            
            # Check for missing tickets (Closed)
            closed_tickets = self.known_tickets - current_tickets
            if closed_tickets:
                from notifications.telegram_notifier import notify_trade_closed
                for t in closed_tickets:
                    deals = mt5.history_deals_get(position=t)
                    if deals:
                        close_deal = deals[-1]
                        if (
                            close_deal.entry == mt5.DEAL_ENTRY_OUT
                            and getattr(close_deal, "magic", settings.MAGIC_NUMBER) == settings.MAGIC_NUMBER
                        ):
                            profit = close_deal.profit
                            symbol = close_deal.symbol
                            direction = closing_deal_position_direction(close_deal.type)
                            notify_trade_closed(t, symbol, direction, profit, None)
            
            self.known_tickets = current_tickets
        except Exception as e:
            logger.error(f"Error checking closed positions: {e}")

    def _handle_command(self, cmd_text):
        parts = cmd_text.strip().split()
        if not parts: return
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/status":
            self._cmd_status()
        elif cmd == "/positions":
            self._cmd_positions()
        elif cmd == "/closeall":
            self._cmd_closeall()
        elif cmd == "/pause":
            self._cmd_pause(args[0] if args else None)
        elif cmd == "/resume":
            self._cmd_resume(args[0] if args else None)
        elif cmd == "/stop":
            self._cmd_stop()
        elif cmd == "/stats":
            self._cmd_stats()
        elif cmd == "/report":
            self._cmd_report()
        elif cmd == "/risk":
            self._cmd_risk()
        elif cmd == "/top":
            self._cmd_top()
        elif cmd == "/health":
            self._cmd_health()
        elif cmd == "/scoreboard":
            self._cmd_scoreboard()
        elif cmd == "/learning":
            self._cmd_learning()
        elif cmd == "/insights":
            self._cmd_insights()
        elif cmd == "/ready":
            self._cmd_ready()
        elif cmd == "/spreadmem":
            self._cmd_spreadmem()
        elif cmd == "/review":
            self._cmd_review()
        elif cmd == "/pa":
            self._cmd_pa()
        elif cmd == "/missed":
            self._cmd_missed()
        elif cmd == "/sim":
            self._cmd_sim()
        elif cmd == "/simtop":
            self._cmd_sim_context("top")
        elif cmd == "/simbad":
            self._cmd_sim_context("bad")
        elif cmd == "/monitor":
            self._cmd_monitor()
        elif cmd == "/promote" and args:
            self._cmd_promote(args[0])
        else:
            send_telegram("❌ Unknown command.")
            send_telegram("❌ Unknown command.\nAvailable: /status, /positions, /pause, /resume, /stop, /stats, /report, /risk, /top, /health, /scoreboard, /learning, /insights, /ready, /spreadmem, /review, /pa, /missed, /sim, /simtop, /simbad, /monitor")

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

    def _cmd_closeall(self):
        try:
            pos = mt5.positions_get() or []
            if not pos:
                send_telegram("0️⃣ No open positions to close.")
                return
            count = 0
            for p in pos:
                # Force close by emitting an intent with 0 quantity? Or use MT5 API directly?
                close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
                tick = mt5.symbol_info_tick(p.symbol)
                if tick:
                    price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": p.symbol,
                        "volume": p.volume,
                        "type": close_type,
                        "position": p.ticket,
                        "price": price,
                        "deviation": 20,
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    res = mt5.order_send(request)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        count += 1
            send_telegram(f"✅ <b>Closed {count}/{len(pos)} positions.</b>")
        except Exception as e:
            send_telegram(f"❌ Error closing all: {e}")

    def _cmd_pause(self, symbol=None):
        if symbol:
            self.alpha_worker.manual_paused_symbols.add(symbol)
            send_telegram(f"⏸️ <b>{symbol} PAUSED</b>\nNo new trades will be opened for {symbol}.")
        else:
            self.alpha_worker.is_paused = True
            send_telegram("⏸️ <b>Bot PAUSED</b>\nNo new trades will be opened for ALL symbols.")

    def _cmd_resume(self, symbol=None):
        if symbol:
            if symbol in self.alpha_worker.manual_paused_symbols:
                self.alpha_worker.manual_paused_symbols.remove(symbol)
            send_telegram(f"▶️ <b>{symbol} RESUMED</b>\nTrading logic will resume for {symbol}.")
            return
        
        try:
            from gqos.ops.live_guard import get_entry_block_reason
            acc = mt5.account_info()
            balance = float(getattr(acc, "balance", 0.0)) if acc else 0.0
            block_reason = get_entry_block_reason(balance)
            if block_reason:
                if settings.LIVE_GUARD_ENTRY_ACTION == "PROBE":
                    self.alpha_worker.is_paused = False
                    self.alpha_worker.guard_probe_reason = block_reason
                    send_telegram(
                        "🧪 <b>Guarded probe mode enabled</b>\n"
                        f"{block_reason}\n"
                        f"New entries are limited to {settings.LIVE_GUARD_PROBE_MULTIPLIER:.2f}x size."
                    )
                    return
                self.alpha_worker.is_paused = True
                send_telegram(
                    "⛔ <b>Resume blocked by Live Guard</b>\n"
                    f"{block_reason}\n"
                    "Existing positions are still being managed."
                )
                return
        except Exception as e:
            logger.warning(f"Resume guard check failed: {e}")
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
        except Exception:
            pass

        pending_count = 0
        try:
            with open("data/learning/pending_trades.json", "r") as f:
                pending_count = len(json.load(f))
        except Exception:
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

    def _cmd_health(self):
        try:
            import html
            from gqos.ops.live_guard import build_health_report, summarize_rejection_reasons
            ok, report = build_health_report()
            prefix = "PASS" if ok else "CHECK"
            send_telegram(f"<b>GQOS Health</b> [{prefix}]\n<pre>{html.escape(report)}</pre>")
            send_telegram(f"<pre>{html.escape(summarize_rejection_reasons())}</pre>")
        except Exception as e:
            send_telegram(f"❌ Health check failed: {e}")

    def _cmd_scoreboard(self):
        try:
            from gqos.ops.live_guard import build_symbol_scoreboard
            send_telegram(build_symbol_scoreboard(max_rows=25))
        except Exception as e:
            send_telegram(f"❌ Scoreboard failed: {e}")

    def _cmd_learning(self):
        try:
            from gqos.ops.learning_health import build_learning_health
            ok, report = build_learning_health()
            prefix = "PASS" if ok else "CHECK"
            send_telegram(f"<b>Learning Health</b> [{prefix}]\n<pre>{html.escape(report)}</pre>")
        except Exception as e:
            send_telegram(f"❌ Learning health failed: {e}")

    def _cmd_insights(self):
        try:
            from gqos.ops.learning_insights import build_learning_insights_report
            send_telegram(f"<b>Learning Insights</b>\n<pre>{html.escape(build_learning_insights_report()[:3500])}</pre>")
        except Exception as e:
            send_telegram(f"❌ Learning insights failed: {e}")

    def _cmd_ready(self):
        try:
            from gqos.ops.recovery_readiness import build_recovery_readiness_report
            send_telegram(f"<b>Recovery Readiness</b>\n<pre>{html.escape(build_recovery_readiness_report())}</pre>")
        except Exception as e:
            send_telegram(f"❌ Recovery readiness failed: {e}")

    def _cmd_spreadmem(self):
        try:
            from gqos.ops.spread_regime_memory import build_spread_regime_report
            send_telegram(f"<b>Spread Regime Memory</b>\n<pre>{html.escape(build_spread_regime_report())}</pre>")
        except Exception as e:
            send_telegram(f"❌ Spread memory failed: {e}")

    def _cmd_review(self):
        try:
            from gqos.learning.post_trade_review import build_post_trade_review_report
            send_telegram(f"<b>Post-Trade Review</b>\n<pre>{html.escape(build_post_trade_review_report())}</pre>")
        except Exception as e:
            send_telegram(f"❌ Post-trade review failed: {e}")

    def _cmd_pa(self):
        try:
            from gqos.ops.pa_filter_analytics import build_pa_filter_report
            send_telegram(f"<b>Price Action Filter Analytics</b>\n<pre>{html.escape(build_pa_filter_report()[:3500])}</pre>")
        except Exception as e:
            send_telegram(f"❌ PA analytics failed: {e}")

    def _cmd_missed(self):
        try:
            from gqos.learning.missed_opportunity_tracker import missed_opportunity_tracker
            from gqos.ops.missed_opportunity_report import build_missed_opportunity_report
            missed_opportunity_tracker.process_pending(limit=None)
            send_telegram(f"<b>Missed Opportunity</b>\n<pre>{html.escape(build_missed_opportunity_report())}</pre>")
        except Exception as e:
            send_telegram(f"❌ Missed opportunity report failed: {e}")

    def _cmd_sim(self):
        try:
            from gqos.learning.continuous_market_simulator import continuous_market_simulator
            from gqos.learning.simulation_analyzer import build_simulation_recommendations
            from gqos.ops.continuous_market_sim_report import build_continuous_market_sim_report
            continuous_market_simulator.scan_once()
            recs = build_simulation_recommendations().get("recommendations", {})
            rec_lines = ["", "Recommendations:"]
            for key, rec in list(recs.items())[:8]:
                rec_lines.append(
                    f"- {key}: {rec.get('action')} AvgR={float(rec.get('avg_r', 0.0)):+.2f} "
                    f"Conf={float(rec.get('confidence', 0.0)):.0%} "
                    f"PFadj={float(rec.get('pf_threshold_adjust', 0.0)):+.3f}"
                )
            report = build_continuous_market_sim_report()
            if recs:
                report += "\n" + "\n".join(rec_lines)
            send_telegram(f"<b>Continuous Market Simulation</b>\n<pre>{html.escape(report)}</pre>")
        except Exception as e:
            send_telegram(f"❌ Continuous simulation report failed: {e}")

    def _cmd_sim_context(self, kind: str):
        try:
            from gqos.learning.simulation_analyzer import build_simulation_recommendations
            from gqos.ops.continuous_market_sim_report import build_sim_context_report
            build_simulation_recommendations()
            title = "Simulation Top Contexts" if kind == "top" else "Simulation Bottom Contexts"
            send_telegram(f"<b>{title}</b>\n<pre>{html.escape(build_sim_context_report(kind=kind, limit=12))}</pre>")
        except Exception as e:
            send_telegram(f"❌ Simulation context report failed: {e}")

    def _cmd_monitor(self):
        try:
            from gqos.ops.learning_health import build_learning_health
            from gqos.ops.continuous_market_sim_report import build_continuous_market_sim_report
            from gqos.ops.missed_opportunity_report import build_missed_opportunity_report
            ok, learning = build_learning_health()
            report = (
                f"Learning: {'PASS' if ok else 'CHECK'}\n"
                f"{learning}\n\n"
                f"{build_continuous_market_sim_report()}\n\n"
                f"{build_missed_opportunity_report()}"
            )
            send_telegram(f"<b>GQOS Monitor</b>\n<pre>{html.escape(report[:3500])}</pre>")
        except Exception as e:
            send_telegram(f"❌ Monitor failed: {e}")

    def _cmd_promote(self, pattern_id):
        db_path = "data/pattern_store/pattern_database.parquet"
        if not os.path.exists(db_path):
            send_telegram("❌ Pattern DB not found.")
            return
            
        try:
            df = pd.read_parquet(db_path)
            mask = df['pattern_id'] == pattern_id
            if not mask.any():
                send_telegram(f"❌ Pattern `{pattern_id}` not found.")
                return
                
            old_status = df.loc[mask, 'promotion_status'].iloc[0]
            df.loc[mask, 'promotion_status'] = "LIVE_APPROVED"
            df.to_parquet(db_path)
            
            send_telegram(f"✅ Pattern `{pattern_id}` manually approved.\nStatus: {old_status} ➡️ LIVE_APPROVED")
            logger.info(f"[TelegramListener] Manual promotion: {pattern_id} from {old_status} to LIVE_APPROVED")
        except Exception as e:
            send_telegram(f"❌ Error promoting: {e}")
            logger.error(f"[TelegramListener] Error promoting {pattern_id}: {e}")
