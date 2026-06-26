"""
gqos/live/daily_scheduler.py
 
Daily Report Scheduler — ส่ง report ทาง Telegram ทุกวันตอน 08:00 UTC
 
วิธีใช้ใน run_gqos_live.py:
    from gqos.live.daily_scheduler import DailyReportScheduler
    scheduler = DailyReportScheduler(report_hour_utc=8)
    scheduler.start()
    # ...
    scheduler.stop()  # ใน shutdown
"""
import logging
import threading
import time
from datetime import datetime, timezone
 
import MetaTrader5 as mt5
 
logger = logging.getLogger("GQOS.DailyScheduler")
 
 
def _get_session(hour_utc: int) -> str:
    if 7  <= hour_utc < 10: return "London"
    if 13 <= hour_utc < 16: return "NY"
    if 16 <= hour_utc < 24: return "Asia_Early"
    if 0  <= hour_utc <  4: return "Asia_Late"
    if 4  <= hour_utc <  7: return "Dead_PreLondon"
    return "Dead_Lunch"
 
 
class DailyReportScheduler:
    def __init__(self, report_hour_utc: int = 8):
        self._hour    = report_hour_utc
        self._running = False
        self._thread  = None
        self._last_report_date = None
 
    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"DailyReportScheduler started. Will report at {self._hour:02d}:00 UTC daily.")
 
    def stop(self):
        self._running = False
        logger.info("DailyReportScheduler stopped.")
 
    def _run_loop(self):
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                today = now.date()
 
                if now.hour == self._hour and self._last_report_date != today:
                    self._send_report()
                    self._last_report_date = today
 
            except Exception as e:
                logger.error(f"[DailyScheduler] Error: {e}")
            time.sleep(60)  # เช็คทุก 1 นาที
 
    def _send_report(self):
        try:
            from notifications.telegram_notifier import notify_daily_report
            from gqos.learning.outcome_logger import outcome_logger
            from gqos.learning.retrain_trigger import retrain_trigger
 
            now = datetime.now(timezone.utc)
            acc = mt5.account_info()
            if acc is None:
                logger.warning("[DailyScheduler] MT5 account unavailable")
                return
 
            # ดึง trades วันนี้จาก MT5 history
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            deals = mt5.history_deals_get(
                start_of_day.replace(tzinfo=None),
                now.replace(tzinfo=None)
            ) or []
 
            closed = [d for d in deals if d.entry == 1]  # DEAL_ENTRY_OUT
            wins   = [d for d in closed if d.profit > 0]
            losses = [d for d in closed if d.profit <= 0]
            daily_pnl   = sum(d.profit for d in closed)
            best_trade  = max((d.profit for d in closed), default=0.0)
            worst_trade = min((d.profit for d in closed), default=0.0)
 
            # Session breakdown
            from collections import defaultdict
            session_stats = defaultdict(lambda: {"n": 0, "wins": 0, "losses": 0, "win_rate": 0.0})
            for d in closed:
                dt   = datetime.utcfromtimestamp(d.time)
                sess = _get_session(dt.hour)
                session_stats[sess]["n"] += 1
                if d.profit > 0:
                    session_stats[sess]["wins"] += 1
                else:
                    session_stats[sess]["losses"] += 1
 
            for sess, s in session_stats.items():
                s["win_rate"] = s["wins"] / s["n"] * 100 if s["n"] > 0 else 0.0
 
            # Learning stats
            stats           = outcome_logger.get_stats()
            retrain_state   = retrain_trigger.get_status()
 
            notify_daily_report(
                balance=float(acc.balance),
                equity=float(acc.equity),
                daily_pnl=daily_pnl,
                total_trades=len(closed),
                wins=len(wins),
                losses=len(losses),
                best_trade=best_trade,
                worst_trade=worst_trade,
                live_trades_total=stats.get("total", 0),
                retrain_progress=retrain_state.get("trades_since_retrain", 0),
                retrain_threshold=retrain_trigger.retrain_threshold,
                session_stats=dict(session_stats),
            )
            logger.info("[DailyScheduler] Daily report sent.")
 
        except Exception as e:
            logger.error(f"[DailyScheduler] Failed to send report: {e}", exc_info=True)
