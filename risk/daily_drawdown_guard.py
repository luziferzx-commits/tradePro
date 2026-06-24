"""risk/daily_drawdown_guard.py — Max daily loss kill switch."""
import logging
from datetime import datetime, timezone
import MetaTrader5 as mt5
from config.settings import settings

logger = logging.getLogger(__name__)


class DailyDrawdownGuard:

    @staticmethod
    def get_daily_pnl() -> float:
        """
        Returns today's REALIZED P&L in account currency (float).
        Queries MT5 history_deals_get() from midnight UTC today.
        Returns 0.0 on any error (fail-open).
        Only counts DEAL_ENTRY_OUT (closing deals) to avoid double counting.
        """
        try:
            today_midnight = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            now = datetime.now(timezone.utc)
            deals = mt5.history_deals_get(today_midnight, now)
            if deals is None:
                logger.debug("MT5 history_deals_get returned None.")
                return 0.0
            pnl = sum(
                d.profit for d in deals
                if d.entry == mt5.DEAL_ENTRY_OUT
            )
            return float(pnl)
        except Exception as e:
            logger.warning(f"DailyDrawdownGuard.get_daily_pnl() error: {e}")
            return 0.0

    @staticmethod
    def is_safe() -> tuple[bool, str]:
        """
        Returns (True, reason_str) if safe to trade today.
        Returns (False, reason_str) if daily loss limit exceeded.
        Fail-open: returns (True, 'check_failed') on any MT5 error.
        """
        try:
            acc = mt5.account_info()
            if acc is None:
                logger.warning("DailyDrawdownGuard: MT5 account_info() returned None.")
                return True, "check_failed_no_account"

            balance = float(acc.balance)
            if balance <= 0:
                logger.warning("DailyDrawdownGuard: balance is zero or negative.")
                return True, "check_failed_zero_balance"

            daily_pnl = DailyDrawdownGuard.get_daily_pnl()

            # Profitable day — always safe
            if daily_pnl >= 0:
                return True, f"profitable_day pnl=+{daily_pnl:.2f}"

            daily_loss_pct = abs(daily_pnl) / balance

            # Hard kill threshold
            if hasattr(settings, "MAX_DAILY_LOSS_PCT"):
                max_daily_loss = settings.MAX_DAILY_LOSS_PCT
            else:
                max_daily_loss = 0.03
                
            if hasattr(settings, "MAX_DAILY_LOSS_WARNING_PCT"):
                warning_pct = settings.MAX_DAILY_LOSS_WARNING_PCT
            else:
                warning_pct = 0.02

            if daily_loss_pct >= max_daily_loss:
                reason = (
                    f"DAILY LOSS LIMIT HIT: {daily_loss_pct:.1%} "
                    f">= {max_daily_loss:.1%} "
                    f"(pnl={daily_pnl:.2f} balance={balance:.2f})"
                )
                logger.critical(f"🛑 {reason}")
                return False, reason

            # Warning threshold — continue trading but alert
            if daily_loss_pct >= warning_pct:
                reason = (
                    f"WARNING daily_loss={daily_loss_pct:.1%} "
                    f"approaching limit {max_daily_loss:.1%}"
                )
                logger.warning(f"⚠ DailyDrawdownGuard: {reason}")
                return True, reason

            return True, f"OK loss={daily_loss_pct:.1%}"

        except Exception as e:
            logger.warning(f"DailyDrawdownGuard.is_safe() exception: {e}")
            return True, "check_failed_exception"
