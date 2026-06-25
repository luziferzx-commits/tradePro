"""risk/portfolio_drawdown_guard.py — Portfolio-level max daily drawdown kill switch."""
import logging
from datetime import datetime, timezone
import MetaTrader5 as mt5
from config.settings import settings

logger = logging.getLogger(__name__)

class PortfolioDrawdownGuard:
    @staticmethod
    def get_portfolio_pnl() -> float:
        """
        Returns today's REALIZED + UNREALIZED P&L in account currency.
        """
        try:
            today_midnight = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            now = datetime.now(timezone.utc)
            
            # Realized P&L
            deals = mt5.history_deals_get(today_midnight, now)
            realized_pnl = 0.0
            if deals is not None:
                realized_pnl = sum(
                    d.profit for d in deals
                    if d.entry == mt5.DEAL_ENTRY_OUT
                )
                
            # Unrealized P&L
            positions = mt5.positions_get()
            unrealized_pnl = 0.0
            if positions is not None:
                unrealized_pnl = sum(p.profit for p in positions)
                
            return float(realized_pnl + unrealized_pnl)
        except Exception as e:
            logger.warning(f"PortfolioDrawdownGuard.get_portfolio_pnl() error: {e}")
            return 0.0

    @staticmethod
    def is_safe() -> tuple[bool, str]:
        """
        Returns (True, reason_str) if safe to trade today across the whole portfolio.
        Returns (False, reason_str) if portfolio daily loss limit exceeded.
        Fail-open: returns (True, 'check_failed') on any MT5 error.
        """
        try:
            acc = mt5.account_info()
            if acc is None:
                logger.warning("PortfolioDrawdownGuard: MT5 account_info() returned None.")
                return True, "check_failed_no_account"

            balance = float(acc.balance)
            if balance <= 0:
                logger.warning("PortfolioDrawdownGuard: balance is zero or negative.")
                return True, "check_failed_zero_balance"

            portfolio_pnl = PortfolioDrawdownGuard.get_portfolio_pnl()

            # Profitable day — always safe
            if portfolio_pnl >= 0:
                return True, f"profitable_day pnl=+{portfolio_pnl:.2f}"

            daily_loss_pct = abs(portfolio_pnl) / balance

            # Hard kill threshold for portfolio
            max_daily_loss = getattr(settings, "MAX_PORTFOLIO_DAILY_LOSS_PCT", 0.05)
            warning_pct = getattr(settings, "MAX_PORTFOLIO_DAILY_LOSS_WARNING_PCT", 0.03)

            if daily_loss_pct >= max_daily_loss:
                reason = (
                    f"PORTFOLIO LOSS LIMIT HIT: {daily_loss_pct:.1%} "
                    f">= {max_daily_loss:.1%} "
                    f"(pnl={portfolio_pnl:.2f} balance={balance:.2f})"
                )
                logger.critical(f"🛑 KILL SWITCH TRIGGERED: {reason}")
                return False, reason

            # Warning threshold
            if daily_loss_pct >= warning_pct:
                reason = (
                    f"WARNING portfolio_loss={daily_loss_pct:.1%} "
                    f"approaching limit {max_daily_loss:.1%}"
                )
                logger.warning(f"⚠ PortfolioDrawdownGuard: {reason}")
                return True, reason

            return True, f"OK portfolio_loss={daily_loss_pct:.1%}"

        except Exception as e:
            logger.warning(f"PortfolioDrawdownGuard.is_safe() exception: {e}")
            return True, "check_failed_exception"
