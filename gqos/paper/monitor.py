from typing import Dict, Tuple
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.paper.events import MarketDataEvent, FeatureDriftEvent

class RealTimeDriftMonitor:
    def __init__(self, event_bus: IEventBus):
        self._event_bus = event_bus
        # Map of feature_id -> (expected_mean, std_dev)
        self._feature_boundaries: Dict[str, Tuple[float, float]] = {}
        self._z_score_threshold = 3.0
        
        self._event_bus.subscribe(MarketDataEvent, self._handle_market_data)
        
    def set_boundary(self, feature_id: str, mean: float, std_dev: float, threshold: float = 3.0):
        self._feature_boundaries[feature_id] = (mean, std_dev)
        self._z_score_threshold = threshold
        
    def _handle_market_data(self, envelope: MessageEnvelope[MarketDataEvent]):
        tick = envelope.payload
        if not tick.data:
            return
            
        for key, value in tick.data.items():
            if key in self._feature_boundaries:
                expected_mean, std_dev = self._feature_boundaries[key]
                if std_dev == 0:
                    continue
                    
                z_score = abs(value - expected_mean) / std_dev
                
                if z_score > self._z_score_threshold:
                    event = FeatureDriftEvent(
                        feature_id=key,
                        expected_mean=expected_mean,
                        actual_value=value,
                        z_score_deviation=z_score
                    )
                    self._event_bus.publish(MessageEnvelope.create(payload=event, version=1))
                    # Note: Drift telemetry is warning only, does not halt execution.
