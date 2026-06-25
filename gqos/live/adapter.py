import threading
import time
from typing import Callable, Dict, Optional
from decimal import Decimal

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import HeartbeatEvent, OrderStatus
from gqos.live.interfaces import IBrokerAdapter
from gqos.common.enums import TradeDirection

class SandboxBrokerAdapter(IBrokerAdapter):
    def __init__(self, event_bus: IEventBus, oms_callback: Callable):
        self._event_bus = event_bus
        self._oms_callback = oms_callback
        
        self._running = False
        self._thread = None
        self._heartbeat_interval = 1.0
        
        # Simulate positions on the exchange to test Reconciliation
        self.actual_positions: Dict[str, Decimal] = {}
        
        self._simulate_disconnect = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()

    def trigger_disconnect(self):
        self._simulate_disconnect = True
        
    def reconnect(self):
        self._simulate_disconnect = False

    def get_actual_positions(self) -> Dict[str, Decimal]:
        """Queries 'Broker' for true positions"""
        if self._simulate_disconnect:
            raise ConnectionError("Broker disconnected")
        return self.actual_positions.copy()

    def submit_order(self, order_id: str, symbol: str, direction: TradeDirection, quantity: Decimal, price: Decimal, stop_loss: Optional[Decimal] = None, take_profit: Optional[Decimal] = None):
        """
        Simulates submitting an order to an exchange.
        """
        if self._simulate_disconnect:
            self._oms_callback(order_id, "REJECT", None, None, "Connection Lost")
            return
            
        # Simulate network latency
        time.sleep(0.05)
        
        # ACK
        self._oms_callback(order_id, OrderStatus.ACK.value, None, None, "Order Accepted")
        
        # Simulate partial fills
        # Threaded async fills
        threading.Thread(target=self._simulate_fill_process, args=(order_id, symbol, quantity, price), daemon=True).start()

    def _simulate_fill_process(self, order_id: str, symbol: str, quantity: Decimal, price: Decimal):
        time.sleep(0.1) # Time to fill
        
        if self._simulate_disconnect:
            # Exchange canceled order due to disconnect
            self._oms_callback(order_id, OrderStatus.CANCELLED.value, None, None, "Exchange Cancelled")
            return
            
        # First partial fill (50%)
        half_qty = quantity / Decimal('2')
        self._oms_callback(order_id, "FILL", half_qty, price, "")
        
        # Update our internal sandbox true position
        current = self.actual_positions.get(symbol, Decimal('0'))
        self.actual_positions[symbol] = current + half_qty
        
        time.sleep(0.1)
        
        # Second partial fill (50%)
        self._oms_callback(order_id, "FILL", half_qty, price, "")
        self.actual_positions[symbol] += half_qty

    def cancel_order(self, order_id: str):
        if self._simulate_disconnect:
            raise ConnectionError("Cannot cancel, broker disconnected")
        self._oms_callback(order_id, OrderStatus.CANCELLED.value, None, None, "User Requested Cancel")

    def _run_loop(self):
        while self._running:
            if not self._simulate_disconnect:
                hb = HeartbeatEvent(
                    timestamp=time.time(),
                    latency_ms=10.5,
                    status="OK"
                )
                self._event_bus.publish(MessageEnvelope.create(payload=hb, version=1))
            time.sleep(self._heartbeat_interval)
