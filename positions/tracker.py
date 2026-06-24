import logging
import MetaTrader5 as mt5
from database.repository import repository
from database.models import TradeRecord
from database.logger import DatabaseLogger
from datetime import datetime

logger = logging.getLogger(__name__)

class PositionTracker:
    @staticmethod
    def sync_open_positions():
        """
        Checks MT5 for closed positions and updates the database.
        """
        with repository.get_session() as session:
            db_open_trades = session.query(TradeRecord).filter(TradeRecord.status == 'OPEN').all()
            
            if not db_open_trades:
                return
                
            mt5_positions = mt5.positions_get()
            mt5_tickets = [p.ticket for p in mt5_positions] if mt5_positions else []
            
            for db_trade in db_open_trades:
                if db_trade.ticket not in mt5_tickets:
                    # Trade has been closed
                    history_deals = mt5.history_deals_get(position=db_trade.ticket)
                    if history_deals:
                        # Find the closing deal
                        close_deal = history_deals[-1]
                        DatabaseLogger.log_trade_close(
                            ticket=db_trade.ticket,
                            close_price=close_deal.price,
                            close_time=datetime.fromtimestamp(close_deal.time),
                            pnl=close_deal.profit
                        )
                        logger.info(f"Trade {db_trade.ticket} closed. PnL: {close_deal.profit}")
                        
                        from notifications.telegram_notifier import notify_trade_closed
                        try:
                            risk_usd = float(db_trade.volume) * 100 * abs(float(db_trade.open_price) - float(db_trade.sl)) if db_trade.volume else 0
                            rr = close_deal.profit / risk_usd if risk_usd > 0 else 0
                        except Exception:
                            rr = 0
                        notify_trade_closed(db_trade.ticket, db_trade.direction, close_deal.profit, rr)
