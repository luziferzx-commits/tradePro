import logging
import MetaTrader5 as mt5
from datetime import datetime, time as dt_time, timedelta
from config.settings import settings
from risk.manager import RiskManager
from risk.portfolio_manager import portfolio_manager

logger = logging.getLogger("GoldBot.RiskGuard")

class RiskGuard:
    @staticmethod
    def _get_start_of_day():
        now = datetime.now()
        return datetime.combine(now.date(), dt_time())

    @staticmethod
    def _calculate_daily_loss(account_info) -> tuple[float, str]:
        """Returns drawdown_pct, calculation_method"""
        start_of_day = RiskGuard._get_start_of_day()
        end_of_day = start_of_day + timedelta(days=1)
        
        deals = mt5.history_deals_get(start_of_day, end_of_day)
        
        if deals is not None:
            # Sum realized PnL for today
            realized_pnl = sum(d.profit for d in deals if d.magic == settings.MAGIC_NUMBER)
            
            # Estimate start-of-day balance (current balance - today's PnL)
            start_balance = account_info.balance - realized_pnl
            
            if start_balance > 0 and realized_pnl < 0:
                drawdown_pct = abs(realized_pnl) / start_balance
                return drawdown_pct, "MT5_HISTORY"
            return 0.0, "MT5_HISTORY"
            
        else:
            # Fallback
            drawdown_pct = (account_info.balance - account_info.equity) / account_info.balance if account_info.balance > 0 else 0.0
            return max(0.0, drawdown_pct), "EQUITY_FALLBACK"

    @staticmethod
    def _count_trades_today() -> int:
        start_of_day = RiskGuard._get_start_of_day()
        end_of_day = start_of_day + timedelta(days=1)
        
        deals = mt5.history_deals_get(start_of_day, end_of_day)
        if deals is None:
            return 0
            
        # Count unique entry deals
        entry_deals = [d for d in deals if d.magic == settings.MAGIC_NUMBER and d.entry == mt5.DEAL_ENTRY_IN]
        return len(entry_deals)

    @staticmethod
    def evaluate_trade(symbol: str, direction: str, signal_price: float, sl_points: float, tp_points: float, ml_prob: float, health_score: int = 100) -> dict:
        """
        Unified Hard Guard execution. Returns a structured decision dict.
        """
        decision = {
            "allowed": False,
            "reason": "",
            "risk_amount": 0.0,
            "position_size": 0.0,
            "guard_that_failed": None
        }

        # 1. Connection Guard
        term_info = mt5.terminal_info()
        if term_info is None or not term_info.connected:
            decision["reason"] = "MT5 Disconnected"
            decision["guard_that_failed"] = "CONNECTION"
            return decision

        # 2. Account Guard
        account_info = mt5.account_info()
        if not account_info:
            decision["reason"] = "Failed to get account info"
            decision["guard_that_failed"] = "ACCOUNT_READ"
            return decision

        if not settings.ALLOW_LIVE_TRADING and account_info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            decision["reason"] = "Live trading blocked by ALLOW_LIVE_TRADING=False"
            decision["guard_that_failed"] = "LIVE_ACCOUNT_RESTRICTION"
            return decision

        if account_info.equity < settings.MIN_EQUITY:
            decision["reason"] = f"Equity below minimum limit ({account_info.equity} < {settings.MIN_EQUITY})"
            decision["guard_that_failed"] = "MIN_EQUITY"
            return decision

        # 3. Parameter Guards
        if settings.REQUIRE_STOP_LOSS and sl_points <= 0:
            decision["reason"] = "Stop Loss is required but missing or <= 0"
            decision["guard_that_failed"] = "MISSING_SL"
            return decision

        if settings.REQUIRE_TAKE_PROFIT and tp_points <= 0:
            decision["reason"] = "Take Profit is required but missing or <= 0"
            decision["guard_that_failed"] = "MISSING_TP"
            return decision

        # 4. Symbol & Spread Guard
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            decision["reason"] = f"Symbol {symbol} not found"
            decision["guard_that_failed"] = "SYMBOL_NOT_FOUND"
            return decision

        if not symbol_info.session_deals:
            decision["reason"] = "Market session is closed for trading"
            decision["guard_that_failed"] = "SESSION_CLOSED"
            return decision

        if symbol_info.spread > settings.MAX_SPREAD_POINTS:
            decision["reason"] = f"Spread too high ({symbol_info.spread} > {settings.MAX_SPREAD_POINTS})"
            decision["guard_that_failed"] = "MAX_SPREAD"
            return decision

        # 5. Pre-Trade Slippage (Price Drift) Guard
        current_price = mt5.symbol_info_tick(symbol).ask if direction == "BUY" else mt5.symbol_info_tick(symbol).bid
        price_drift_points = abs(current_price - signal_price) / symbol_info.point
        if price_drift_points > settings.MAX_SLIPPAGE_POINTS:
            decision["reason"] = f"Signal price drifted too far ({price_drift_points:.1f} pts > {settings.MAX_SLIPPAGE_POINTS})"
            decision["guard_that_failed"] = "PRICE_DRIFT_EXCEEDED"
            return decision

        # 6. Portfolio Limits
        trades_today = RiskGuard._count_trades_today()
        if trades_today >= settings.MAX_TRADES_PER_DAY:
            decision["reason"] = f"Max trades per day reached ({trades_today} >= {settings.MAX_TRADES_PER_DAY})"
            decision["guard_that_failed"] = "MAX_TRADES_PER_DAY"
            return decision

        approved, p_reason = portfolio_manager.can_open_trade(symbol, settings.RISK_PER_TRADE_PCT)
        if not approved:
            decision["reason"] = f"Portfolio Manager rejected: {p_reason}"
            decision["guard_that_failed"] = "PORTFOLIO_LIMIT"
            return decision

        # 7. Drawdown & Loss Guards
        daily_loss_pct, loss_calc_method = RiskGuard._calculate_daily_loss(account_info)
        if daily_loss_pct > settings.MAX_DAILY_LOSS_PCT:
            decision["reason"] = f"Daily Loss Limit Hit ({daily_loss_pct*100:.2f}% > {settings.MAX_DAILY_LOSS_PCT*100:.2f}%) using {loss_calc_method}"
            decision["guard_that_failed"] = "MAX_DAILY_LOSS"
            return decision

        # General Drawdown
        current_drawdown = (account_info.balance - account_info.equity) / account_info.balance if account_info.balance > 0 else 0
        if current_drawdown > settings.MAX_DRAWDOWN_PCT:
            decision["reason"] = f"Max Drawdown Hit ({current_drawdown*100:.2f}% > {settings.MAX_DRAWDOWN_PCT*100:.2f}%)"
            decision["guard_that_failed"] = "MAX_DRAWDOWN"
            return decision

        # Consecutive Losses (We rely on CircuitBreaker logic, which we can extract or just call it if we want, but let's implement here)
        from safety.circuit_breaker import CircuitBreaker
        if not CircuitBreaker.check_consecutive_losses():
            decision["reason"] = "Max consecutive losses limit hit"
            decision["guard_that_failed"] = "CONSECUTIVE_LOSSES"
            return decision

        # 8. Sizing Calculation
        volume = RiskManager.calculate_position_size(symbol, sl_points, ml_prob, 0.0, health_score)
        
        if volume <= 0:
            decision["reason"] = "Calculated position size is 0 (risk too low or volume below min_lot)"
            decision["guard_that_failed"] = "POSITION_SIZE_ZERO"
            return decision

        # Verify against explicit cap
        loss_per_lot = (sl_points * symbol_info.point) * (symbol_info.trade_tick_value / symbol_info.trade_tick_size)
        risk_amount = volume * loss_per_lot
        max_allowed_risk = account_info.balance * settings.RISK_PER_TRADE_PCT
        
        if risk_amount > max_allowed_risk:
            # Hard enforce cap
            decision["reason"] = f"Risk {risk_amount} exceeds cap {max_allowed_risk}"
            decision["guard_that_failed"] = "RISK_EXCEEDS_CAP"
            return decision

        # All passed
        decision["allowed"] = True
        decision["reason"] = "All guards passed"
        decision["risk_amount"] = round(risk_amount, 2)
        decision["position_size"] = volume

        return decision
