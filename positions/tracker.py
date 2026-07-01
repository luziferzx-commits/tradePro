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
                        
                        duration_seconds = None
                        try:
                            if db_trade.open_time:
                                close_time_dt = datetime.fromtimestamp(close_deal.time)
                                duration_seconds = (close_time_dt - db_trade.open_time).total_seconds()
                        except Exception:
                            pass
                            
                        notify_trade_closed(db_trade.ticket, db_trade.symbol, db_trade.direction, close_deal.profit, rr, 0.0, duration_seconds)

    @staticmethod
    def manage_trailing_stops():
        """
        Implements Break-Even and Trailing Stop logic for all open MT5 positions.
        - Break-Even: If price reaches +1R, move SL to Entry.
        - Trailing: If price reaches +2R, move SL to +1R.
        """
        mt5_positions = mt5.positions_get()
        if not mt5_positions:
            return
            
        with repository.get_session() as session:
            db_open_trades = session.query(TradeRecord).filter(TradeRecord.status == 'OPEN').all()
            db_trade_map = {t.ticket: t for t in db_open_trades}
            
            for p in mt5_positions:
                db_trade = db_trade_map.get(p.ticket)
                if not db_trade:
                    continue
                    
                entry_price = p.price_open
                current_sl = p.sl
                current_price = p.price_current
                
                # If SL is not set or 0, we can't calculate R
                if current_sl == 0.0 or db_trade.sl == 0.0:
                    continue
                    
                # Calculate initial R distance based on DB original SL
                initial_sl = float(db_trade.sl)
                r_dist = abs(entry_price - initial_sl)
                
                if r_dist <= 0:
                    continue
                
                is_buy = p.type == mt5.POSITION_TYPE_BUY
                
                # Calculate current floating R
                if is_buy:
                    floating_r = (current_price - entry_price) / r_dist
                    break_even_price = entry_price
                    trail_price_1r = entry_price + (r_dist * 0.8) # Trail slightly below 1R to give breathing room
                else:
                    floating_r = (entry_price - current_price) / r_dist
                    break_even_price = entry_price
                    trail_price_1r = entry_price - (r_dist * 0.8)

                new_sl = None
                
                # Break-Even at +1R
                if floating_r >= 1.0 and floating_r < 2.0:
                    # Check if SL is not already moved to BE or better
                    if is_buy and current_sl < break_even_price:
                        new_sl = break_even_price
                    elif not is_buy and current_sl > break_even_price:
                        new_sl = break_even_price
                        
                # Trail at +2R
                elif floating_r >= 2.0:
                    if is_buy and current_sl < trail_price_1r:
                        new_sl = trail_price_1r
                    elif not is_buy and current_sl > trail_price_1r:
                        new_sl = trail_price_1r
                        
                if new_sl is not None:
                    # Need to format price to symbol digits
                    sym_info = mt5.symbol_info(p.symbol)
                    if sym_info:
                        new_sl = round(new_sl, sym_info.digits)
                        
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": p.ticket,
                            "symbol": p.symbol,
                            "sl": float(new_sl),
                            "tp": float(p.tp),
                        }
                        
                        result = mt5.order_send(request)
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"Moved SL for {p.symbol} (Ticket: {p.ticket}) to {new_sl} (R={floating_r:.2f})")
                        else:
                            logger.warning(f"Failed to move SL for {p.symbol}: {result.comment}")
