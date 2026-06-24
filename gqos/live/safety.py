import time
from typing import Callable, List
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import HeartbeatEvent

class GlobalKillSwitch:
    def __init__(self, oms, broker_adapter):
        self._oms = oms
        self._broker_adapter = broker_adapter
        self.is_triggered = False
        
    def trigger(self, reason: str):
        if self.is_triggered:
            return
            
        print(f"KILL SWITCH TRIGGERED: {reason}")
        self.is_triggered = True
        
        # Attempt to cancel all open orders
        for order_id, order in self._oms.orders.items():
            if order.status.name in ["NEW", "ACK", "PARTIAL"]:
                try:
                    self._broker_adapter.cancel_order(order_id)
                    print(f"Cancelled open order {order_id}")
                except Exception as e:
                    print(f"Failed to cancel order {order_id}: {e}")
                    
    def check_new_order_allowed(self) -> bool:
        """Called before placing any new order"""
        return not self.is_triggered

class HeartbeatMonitor:
    def __init__(self, event_bus: IEventBus, kill_switch: GlobalKillSwitch, timeout_seconds: float = 3.0):
        self._event_bus = event_bus
        self._kill_switch = kill_switch
        self._timeout_seconds = timeout_seconds
        self._last_heartbeat = time.time()
        
        self._event_bus.subscribe(HeartbeatEvent, self._handle_heartbeat)
        
    def _handle_heartbeat(self, envelope: MessageEnvelope[HeartbeatEvent]):
        self._last_heartbeat = envelope.payload.timestamp
        
    def check_health(self):
        """Called periodically by the Engine loop"""
        if time.time() - self._last_heartbeat > self._timeout_seconds:
            self._kill_switch.trigger("Heartbeat Timeout: Connection to Broker Lost")
