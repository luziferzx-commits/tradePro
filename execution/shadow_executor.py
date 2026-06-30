import logging
from datetime import datetime
import MetaTrader5 as mt5
from database.repository import repository
from database.models import ShadowTrade
from data.mt5_client import mt5_client

logger = logging.getLogger("GoldBot.ShadowExecutor")

class ShadowExecutor:
    @staticmethod
    def execute_trade(signal_id, symbol, direction, volume, sl_points, tp_points=None):
        """
        Executes a virtual trade in SHADOW_MODE. 
        Never calls MT5 order_send.
        """
        logger.info(f"SHADOW_MODE: Executing virtual {direction} trade for {volume} lots on {symbol}.")
        
        resolved_symbol = mt5_client.resolve_symbol(symbol)
        
        # 1. Fetch real-time tick for realistic execution price
        tick = mt5.symbol_info_tick(resolved_symbol)
        if not tick:
            logger.error("Failed to get live tick for shadow trade. Using 0.0.")
            entry_price = 0.0
        else:
            entry_price = tick.ask if direction == "BUY" else tick.bid
            
        if entry_price == 0.0:
            logger.warning("Entry price is 0.0, shadow trade will be inaccurate.")
            
        # 2. Calculate SL and TP
        sym_info = mt5.symbol_info(resolved_symbol)
        point = sym_info.point if sym_info else 0.01
        
        sl_diff = sl_points * point
        tp_diff = (tp_points * point) if tp_points is not None else sl_diff * 2.5
        
        if direction == "BUY":
            sl = entry_price - sl_diff
            tp = entry_price + tp_diff
        else:
            sl = entry_price + sl_diff
            tp = entry_price - tp_diff
            
        # 3. Store in Database
        with repository.get_session() as session:
            shadow = ShadowTrade(
                signal_id=signal_id,
                symbol=symbol,
                direction=direction,
                volume=volume,
                open_time=datetime.utcnow(),
                open_price=entry_price,
                sl=sl,
                tp=tp,
                status="OPEN"
            )
            session.add(shadow)
            session.commit()
            
            logger.info(f"ShadowTrade logged successfully [ID: {shadow.id}] | Entry: {entry_price} SL: {sl} TP: {tp}")
