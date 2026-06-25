import time
import threading
from typing import Callable, Dict, Optional
from decimal import Decimal

from gqos.common.enums import TradeDirection
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import HeartbeatEvent, OrderStatus, OrderAdjustedEvent
from gqos.live.interfaces import IBrokerAdapter
from gqos.config.secrets import ISecretsProvider

from gqos.live.resilience import TokenBucket
from gqos.live.metadata import MetadataCache

class BinanceAdapter(IBrokerAdapter):
    def __init__(self, event_bus: IEventBus, oms_callback: Callable, secrets_provider: ISecretsProvider, testnet: bool = True):
        self._event_bus = event_bus
        self._oms_callback = oms_callback
        self._secrets = secrets_provider.get_broker_credentials()
        
        if not testnet:
            raise ValueError("BinanceAdapter must be run in testnet mode for M22")
            
        self._base_url = "https://testnet.binance.vision"
        self._ws_url = "wss://testnet.binance.vision/ws"
        
        self._running = False
        self._thread = None
        self._simulate_disconnect = False
        
        # Resilience & Metadata
        self._rate_limiter = TokenBucket(capacity=10, fill_rate=2.0)
        self._metadata = MetadataCache(base_url=self._base_url)
        
    def start(self):
        """Starts the User Data Stream websocket (Simulated for M22)"""
        self._running = True
        self._thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._thread.start()
        
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
            
    def _map_status(self, binance_status: str) -> OrderStatus:
        mapping = {
            "NEW": OrderStatus.NEW,
            "PARTIALLY_FILLED": OrderStatus.PARTIAL,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED
        }
        return mapping.get(binance_status, OrderStatus.REJECTED)

    def _apply_precision(self, value: Decimal, step: Decimal) -> Decimal:
        """Rounds down to nearest step size safely"""
        return (value // step) * step

    def submit_order(self, order_id: str, symbol: str, direction: TradeDirection, quantity: Decimal, price: Decimal, stop_loss: Optional[Decimal] = None, take_profit: Optional[Decimal] = None):
        if not self._rate_limiter.consume(1):
            self._oms_callback(order_id, OrderStatus.REJECTED.value, None, None, "Rate Limit Exceeded (Local Bucket)")
            return
            
        if self._simulate_disconnect:
            self._oms_callback(order_id, OrderStatus.REJECTED.value, None, None, "Websocket Disconnected")
            return
            
        # Apply Exchange Filters (LOT_SIZE, PRICE_FILTER)
        rules = self._metadata.get_rules(symbol)
        adjusted_qty = quantity
        adjusted_price = price
        
        if rules:
            adjusted_qty = self._apply_precision(quantity, rules["step_size"])
            adjusted_price = self._apply_precision(price, rules["tick_size"])
            
            if adjusted_qty != quantity or adjusted_price != price:
                adj_evt = OrderAdjustedEvent(
                    order_id=order_id,
                    symbol=symbol,
                    original_quantity=quantity,
                    adjusted_quantity=adjusted_qty,
                    original_price=price,
                    adjusted_price=adjusted_price,
                    reason=f"Binance LOT_SIZE/PRICE_FILTER adjustment"
                )
                self._event_bus.publish(MessageEnvelope.create(payload=adj_evt, version=1))
                
        if adjusted_qty <= 0:
            self._oms_callback(order_id, OrderStatus.REJECTED.value, None, None, "Quantity adjusted to 0")
            return
            
        # Simulated Network API Call
        time.sleep(0.05)
        
        # Immediately ACK
        self._oms_callback(order_id, OrderStatus.ACK.value, None, None, "Order Accepted")
        
        # Simulate an incoming ExecutionReport via Websocket
        threading.Thread(target=self._simulate_execution_report, args=(order_id, symbol, adjusted_qty, adjusted_price), daemon=True).start()

    def _simulate_execution_report(self, order_id, symbol, quantity, price):
        time.sleep(0.1)
        if self._simulate_disconnect:
            return
            
        # Simulate Partial Fill (Binance payload format)
        payload1 = {
            "e": "executionReport",
            "s": symbol,
            "c": order_id,
            "X": "PARTIALLY_FILLED",
            "l": str(quantity / 2),
            "L": str(price)
        }
        
        self._handle_ws_message(payload1)
        
        time.sleep(0.1)
        if self._simulate_disconnect:
            return
            
        # Simulate Final Fill
        payload2 = {
            "e": "executionReport",
            "s": symbol,
            "c": order_id,
            "X": "FILLED",
            "l": str(quantity / 2),
            "L": str(price)
        }
        
        self._handle_ws_message(payload2)
        
    def _handle_ws_message(self, payload: Dict):
        """Processes incoming raw JSON payloads from Binance Websocket"""
        if payload.get("e") == "executionReport":
            order_id = payload["c"]
            status_str = payload["X"]
            fill_qty = Decimal(payload.get("l", '0'))
            fill_price = Decimal(payload.get("L", '0'))
            
            status_enum = self._map_status(status_str)
            
            if status_enum in [OrderStatus.PARTIAL, OrderStatus.FILLED] and fill_qty > 0:
                self._oms_callback(order_id, "FILL", fill_qty, fill_price, "")
            else:
                self._oms_callback(order_id, status_enum.value, None, None, "Execution Report Update")

    def cancel_order(self, order_id: str):
        if self._simulate_disconnect:
            raise ConnectionError("Disconnected")
        self._oms_callback(order_id, OrderStatus.CANCELLED.value, None, None, "Cancelled via REST")

    def get_actual_positions(self) -> Dict[str, Decimal]:
        # Simulated REST Call
        return {"BTCUSDT": Decimal("1.5"), "ETHUSDT": Decimal("10.0")}

    def _ws_loop(self):
        while self._running:
            if not self._simulate_disconnect:
                hb = HeartbeatEvent(
                    timestamp=time.time(),
                    latency_ms=12.5,
                    status="OK"
                )
                self._event_bus.publish(MessageEnvelope.create(payload=hb, version=1))
            time.sleep(1.0)
            
    def trigger_disconnect(self):
        self._simulate_disconnect = True
