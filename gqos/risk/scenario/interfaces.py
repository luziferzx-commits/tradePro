from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional
from gqos.risk.scenario.models import ScenarioMetadata

class IScenario(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ScenarioMetadata:
        pass

    @property
    @abstractmethod
    def scenario_hash(self) -> str:
        pass

    @abstractmethod
    def get_shock(self, symbol: str, sector: str) -> Optional[Decimal]:
        """
        Returns the shock percentage for a given symbol and sector.
        For example, -0.20 means a -20% impact.
        Returns None if no shock is defined for this symbol/sector.
        """
        pass
