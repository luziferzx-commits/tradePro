from decimal import Decimal
from typing import Dict, Optional
import hashlib
import json
from gqos.risk.scenario.interfaces import IScenario
from gqos.risk.scenario.models import ScenarioMetadata

class BaseScenario(IScenario):
    def __init__(self, metadata: ScenarioMetadata, symbol_shocks: Dict[str, Decimal], sector_shocks: Dict[str, Decimal], global_shock: Decimal = Decimal('0')):
        self._metadata = metadata
        self._symbol_shocks = symbol_shocks or {}
        self._sector_shocks = sector_shocks or {}
        self._global_shock = global_shock
        
        # Calculate a deterministic hash that includes metadata and the shock logic
        data = {
            "metadata_hash": self._metadata.calculate_hash(),
            "symbol_shocks": {k: str(v) for k, v in self._symbol_shocks.items()},
            "sector_shocks": {k: str(v) for k, v in self._sector_shocks.items()},
            "global_shock": str(self._global_shock)
        }
        self._scenario_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

    @property
    def metadata(self) -> ScenarioMetadata:
        return self._metadata

    @property
    def scenario_hash(self) -> str:
        return self._scenario_hash

    def get_shock(self, symbol: str, sector: str) -> Optional[Decimal]:
        if symbol in self._symbol_shocks:
            return self._symbol_shocks[symbol]
        if sector in self._sector_shocks:
            return self._sector_shocks[sector]
        return self._global_shock

class HistoricalScenario(BaseScenario):
    """Represents a specific historical market shock."""
    pass

class HypotheticalScenario(BaseScenario):
    """Represents a hypothetical or user-defined market shock."""
    pass
