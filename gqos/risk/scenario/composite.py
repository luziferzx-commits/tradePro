from decimal import Decimal
from typing import List, Optional
import hashlib
import json
from gqos.risk.scenario.interfaces import IScenario
from gqos.risk.scenario.models import ScenarioMetadata

class CompositeScenario(IScenario):
    """Combines multiple scenarios by summing their shocks."""
    def __init__(self, metadata: ScenarioMetadata, scenarios: List[IScenario]):
        self._metadata = metadata
        self._scenarios = scenarios
        
        data = {
            "metadata_hash": self._metadata.calculate_hash(),
            "scenarios": [s.scenario_hash for s in scenarios]
        }
        self._scenario_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

    @property
    def metadata(self) -> ScenarioMetadata:
        return self._metadata

    @property
    def scenario_hash(self) -> str:
        return self._scenario_hash

    def get_shock(self, symbol: str, sector: str) -> Optional[Decimal]:
        total_shock = Decimal('0')
        applied = False
        for scenario in self._scenarios:
            shock = scenario.get_shock(symbol, sector)
            if shock is not None:
                total_shock += shock
                applied = True
        return total_shock if applied else None
