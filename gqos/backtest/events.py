from dataclasses import dataclass
from typing import Dict, Any, Optional
from gqos.messaging.contracts import Event

@dataclass(frozen=True)
class ForecastEvent(Event):
    forecast_id: str
    alpha_id: str
    timestamp: float
    score: float
    confidence: float
    explanations: Optional[Dict[str, float]] = None

@dataclass(frozen=True)
class TargetPortfolioEvent(Event):
    timestamp: float
    target_weights: Dict[str, float]
