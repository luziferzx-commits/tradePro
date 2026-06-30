from datetime import datetime
import logging
import MetaTrader5 as mt5
from database.logger import DatabaseLogger
from config.settings import settings

logger = logging.getLogger(__name__)

class Executor:
    @staticmethod
    def execute_trade(
        signal_id: int,
        symbol: str,
        direction: str,
        volume: float,
        sl_points: float = 500,
        tp_points: float | None = None,
        probability: float = 0.0,
        evaluation: dict = None,
    ) -> bool:
        """
        Sends an order to MT5. sl_points is in point values (e.g., 500 = 50 pips).
        """
        from risk.portfolio_manager import portfolio_manager
        from data.mt5_client import mt5_client
        
        resolved_symbol = mt5_client.resolve_symbol(symbol)
        
        # Final Safety Assertion Layer
        if not evaluation or not evaluation.get("allowed"):
            logger.error(f"EXECUTION BLOCKED: Trade for {symbol} did not pass RiskGuard evaluation.")
            return False
            
        if volume > evaluation.get("position_size", 0.0) or volume <= 0:
            logger.error(f"EXECUTION BLOCKED: Volume ({volume}) invalid or exceeds approved size ({evaluation.get('position_size', 0)}).")
            return False

        # Enforce LIVE_MICRO_MODE
        if settings.LIVE_MICRO_MODE:
            symbol_info_check = mt5.symbol_info(resolved_symbol)
            min_vol = symbol_info_check.volume_min if symbol_info_check else 0.01
            if volume != min_vol:
                logger.warning(f"LIVE_MICRO_MODE: Forcing volume from {volume} to {min_vol}")
                volume = min_vol
        
        if settings.DRY_RUN:
            logger.info(f"DRY_RUN ACTIVE: Simulated execution for {symbol} {direction} {volume} lots")
            
        if settings.IS_DEMO_ACCOUNT:
            account_info = mt5.account_info()
            if not account_info or account_info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
                logger.error("Execution blocked: Settings demand Demo account but current account is not Demo.")
                return False
                
        # Check max open positions (Replaced by PortfolioManager)
        # We will use PortfolioManager instead
        if not settings.ENABLE_PORTFOLIO_RISK:
            approved, reason = portfolio_manager.can_open_trade(symbol, settings.RISK_PER_TRADE_PCT)
            if not approved:
                logger.warning(f"[Risk] {symbol} rejected: {reason}")
                return False

        if sl_points <= 0:
            logger.error("Execution blocked: SL points must be strictly positive.")
            return False

        symbol_info = mt5.symbol_info(resolved_symbol)
        if symbol_info is None:
            logger.error(f"Symbol {symbol} (resolved: {resolved_symbol}) not found")
            return False

        if not symbol_info.visible:
            if not mt5.symbol_select(resolved_symbol, True):
                logger.error(f"Symbol {symbol} failed to select")
                return False

        point = mt5.symbol_info(resolved_symbol).point
        price = mt5.symbol_info_tick(resolved_symbol).ask if direction == "BUY" else mt5.symbol_info_tick(resolved_symbol).bid
        
        tp_distance_points = tp_points if tp_points is not None else sl_points * 2

        # Calculate SL/TP
        if direction == "BUY":
            order_type = mt5.ORDER_TYPE_BUY
            sl = price - (sl_points * point)
            tp = price + (tp_distance_points * point)
        else:
            order_type = mt5.ORDER_TYPE_SELL
            sl = price + (sl_points * point)
            tp = price - (tp_distance_points * point)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": resolved_symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": settings.MAGIC_NUMBER,
            "comment": "GoldBot AI",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if settings.DRY_RUN:
            logger.info(f"DRY_RUN ON. Intended execution: {request}")
            mock_ticket = int(mt5.symbol_info_tick(resolved_symbol).time)
            DatabaseLogger.log_trade_execution(
                signal_id=signal_id,
                ticket=mock_ticket, # Mock ticket
                symbol=symbol, # Keep original symbol for DB
                direction=direction,
                volume=volume,
                open_price=price,
                sl=sl,
                tp=tp,
                open_time=datetime.utcnow()
            )
            from notifications.telegram_notifier import notify_trade_executed
            notify_trade_executed(symbol, direction, volume, price, sl, tp, mock_ticket, probability)
            return True

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed, retcode={result.retcode}")
            return False
            
        logger.info(f"Order executed successfully! Ticket: {result.order}")
        
        # Log to DB
        DatabaseLogger.log_trade_execution(
            signal_id=signal_id,
            ticket=result.order,
            symbol=symbol, # Keep original symbol for DB
            direction=direction,
            volume=volume,
            open_price=result.price,
            sl=sl,
            tp=tp,
            open_time=datetime.utcnow()
        )
        
        from notifications.telegram_notifier import notify_trade_executed
        notify_trade_executed(symbol, direction, volume, result.price, sl, tp, result.order, probability)
        
        return True
