import logging
import threading
import time
from typing import Callable, Dict, Optional
from decimal import Decimal
import MetaTrader5 as mt5

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import HeartbeatEvent, OrderStatus
from gqos.live.interfaces import IBrokerAdapter
from gqos.common.enums import TradeDirection
from config.settings import settings

logger = logging.getLogger(__name__)

class MT5BrokerAdapter(IBrokerAdapter):
    def __init__(self, event_bus: IEventBus, oms_callback: Callable):
        self._event_bus = event_bus
        self._oms_callback = oms_callback
        
        self._running = False
        self._thread = None
        self._heartbeat_interval = 1.0
        
        # MT5 Initialization is handled globally in GoldBot usually, 
        # but we assume it is already initialized and connected here.
        if not mt5.terminal_info():
            logger.warning("MT5 terminal_info() failed. MT5 might not be initialized.")

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("MT5BrokerAdapter started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        logger.info("MT5BrokerAdapter stopped.")

    def get_actual_positions(self) -> Dict[str, Decimal]:
        """Queries MT5 for true positions to reconcile against GQOS Ledger"""
        positions = {}
        mt5_positions = mt5.positions_get()
        if mt5_positions:
            for p in mt5_positions:
                # MT5 position volume is positive. We assign sign based on direction.
                qty = Decimal(str(p.volume))
                if p.type == mt5.POSITION_TYPE_SELL:
                    qty = -qty
                
                if p.symbol in positions:
                    positions[p.symbol] += qty
                else:
                    positions[p.symbol] = qty
        return positions

    def submit_order(self, order_id: str, symbol: str, direction: TradeDirection, quantity: Decimal, price: Decimal, stop_loss: Optional[Decimal] = None, take_profit: Optional[Decimal] = None):
        """
        Submits an order to MT5.
        Note: The price argument is currently ignored as we execute Market Orders (TRADE_ACTION_DEAL).
        """
        resolved_symbol = symbol
        
        order_type = mt5.ORDER_TYPE_BUY if direction == TradeDirection.BUY else mt5.ORDER_TYPE_SELL
        
        # Fetch current tick to get the market price
        tick = mt5.symbol_info_tick(resolved_symbol)
        if tick is None:
            self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), "Symbol tick not found")
            return
            
        exec_price = tick.ask if direction == TradeDirection.BUY else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": resolved_symbol,
            "volume": float(quantity),
            "type": order_type,
            "price": exec_price,
            "sl": float(stop_loss) if stop_loss else 0.0,
            "tp": float(take_profit) if take_profit else 0.0,
            "deviation": 20,
            "magic": settings.MAGIC_NUMBER,
            "comment": order_id[:10], # Truncate to fit
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Issue MT5 order send
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err_comment = getattr(result, 'comment', 'Unknown MT5 Error')
            logger.error(f"MT5 order_send failed for {order_id}: {err_comment}")
            self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), f"MT5 Error: {err_comment}")
            return
            
        # Success!
        logger.info(f"MT5 Order Executed: {result.order}")
        # We immediately get a fill for Market Orders.
        # Call OMS callback with 'FILL'
        filled_qty = Decimal(str(result.volume))
        filled_price = Decimal(str(result.price))
        
        # First send ACK
        self._oms_callback(order_id, OrderStatus.ACK.value, Decimal('0'), Decimal('0'), "MT5 Accepted")
        
        # Then send FILL
        self._oms_callback(order_id, "FILL", filled_qty, filled_price, f"MT5 Ticket: {result.order}")

    def cancel_order(self, order_id: str):
        """
        Cancels an existing pending order.
        Since we only issue Market Orders (IOC) right now, cancel is not technically used.
        """
        self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), "Cancel not supported for Market Orders")

    def _run_loop(self):
        while self._running:
            # Emit heartbeat
            hb = HeartbeatEvent(
                timestamp=time.time(),
                latency_ms=1.0, # Mock latency
                status="OK"
            )
            self._event_bus.publish(MessageEnvelope.create(payload=hb, version=1))
            time.sleep(self._heartbeat_interval)
