import logging
import MetaTrader5 as mt5
from config.settings import settings
from database.repository import repository
from database.models import TradeRecord

logger = logging.getLogger(__name__)

class CircuitBreaker:
    @staticmethod
    def check_all(symbol: str) -> bool:
        """
        Returns True if safe to trade, False if circuit breaker is triggered.
        """
        if not CircuitBreaker.check_connection():
            return False
            
        if not CircuitBreaker.check_spread(symbol):
            return False
            
        if not CircuitBreaker.check_daily_loss_limit():
            return False
            
        if not CircuitBreaker.check_equity_protection():
            return False
            
        if not CircuitBreaker.check_consecutive_losses():
            return False
            
        return True

    @staticmethod
    def check_connection() -> bool:
        term_info = mt5.terminal_info()
        if term_info is None or not term_info.connected:
            logger.error("Circuit Breaker: MT5 Disconnected!")
            return False
        return True

    @staticmethod
    def check_spread(symbol: str) -> bool:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return False
        
        spread = symbol_info.spread
        if spread > settings.MAX_SPREAD_POINTS:
            logger.warning(f"Circuit Breaker: Spread too high ({spread} > {settings.MAX_SPREAD_POINTS})")
            return False
        return True

    @staticmethod
    def check_daily_loss_limit() -> bool:
        account_info = mt5.account_info()
        if not account_info:
            logger.error("Circuit Breaker: Failed to read MT5 account info")
            return False
            
        # Simplified: Check if equity drops below balance by max %
        # In a real scenario, this requires tracking start-of-day balance
        drawdown_pct = (account_info.balance - account_info.equity) / account_info.balance if account_info.balance > 0 else 0
        if drawdown_pct > settings.MAX_DAILY_LOSS_PCT:
            logger.error(f"Circuit Breaker: Daily Loss Limit Hit ({drawdown_pct*100:.2f}%)")
            return False
        return True

    @staticmethod
    def check_equity_protection() -> bool:
        account_info = mt5.account_info()
        if not account_info:
            logger.error("Circuit Breaker: Failed to read MT5 account info for equity check")
            return False
            
        if account_info.equity < settings.MIN_EQUITY:
            logger.error(f"Circuit Breaker: Equity below minimum limit ({account_info.equity} < {settings.MIN_EQUITY})")
            return False
        return True

    @staticmethod
    def check_consecutive_losses() -> bool:
        with repository.get_session() as session:
            recent_trades = session.query(TradeRecord).filter(TradeRecord.status == 'CLOSED').order_by(TradeRecord.close_time.desc()).limit(settings.MAX_CONSECUTIVE_LOSSES).all()
            
            if len(recent_trades) < settings.MAX_CONSECUTIVE_LOSSES:
                return True
                
            consecutive_losses = sum(1 for t in recent_trades if t.pnl and t.pnl < 0)
            if consecutive_losses == settings.MAX_CONSECUTIVE_LOSSES:
                logger.error(f"Circuit Breaker: Max Consecutive Losses Hit ({settings.MAX_CONSECUTIVE_LOSSES})")
                return False
                
        return True
