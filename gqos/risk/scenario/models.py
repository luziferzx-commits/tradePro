from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Optional
import hashlib
import json

@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    total_impact_amount: Decimal
    total_market_value: Decimal
    portfolio_loss_percent: Decimal
    impact_by_strategy: Dict[str, Decimal]
    impact_by_symbol: Dict[str, Decimal]
    impact_by_sector: Dict[str, Decimal]

@dataclass(frozen=True)
class ScenarioMetadata:
    scenario_id: str
    version: str
    author: str
    created_at: str
    description: str
    assumptions: str
    source: Optional[str] = None
    reference: Optional[str] = None
    event_date: Optional[str] = None
    
    def calculate_hash(self) -> str:
        data = {
            "scenario_id": self.scenario_id,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at,
            "description": self.description,
            "assumptions": self.assumptions,
            "source": self.source,
            "reference": self.reference,
            "event_date": self.event_date
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()
