import pandas as pd
import time
import threading
from typing import Optional

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.paper.events import MarketDataEvent, BarClosedEvent

class SimulatedLiveFeed:
    """
    Simulates a live market feed by reading a static DataFrame and publishing events asynchronously.
    """
    def __init__(self, event_bus: IEventBus, data: pd.DataFrame, symbol: str, interval_ms: int = 100):
        self._bus = event_bus
        self._data = data
        self._symbol = symbol
        self._interval_ms = interval_ms
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()

    def _run_loop(self):
        for index, row in self._data.iterrows():
            if not self._running:
                break
                
            # Simulate a tick arriving
            tick = MarketDataEvent(
                symbol=self._symbol,
                price=float(row['close']),
                timestamp=index.timestamp() if isinstance(index, pd.Timestamp) else time.time(),
                data=row.to_dict()
            )
            self._bus.publish(MessageEnvelope.create(payload=tick, version=1))
            
            # Immediately simulate the bar closing
            bar_closed = BarClosedEvent(
                symbol=self._symbol,
                timestamp=index.timestamp() if isinstance(index, pd.Timestamp) else time.time(),
                bar_data=row
            )
            self._bus.publish(MessageEnvelope.create(payload=bar_closed, version=1))
            
            time.sleep(self._interval_ms / 1000.0)
