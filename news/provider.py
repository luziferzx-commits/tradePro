from abc import ABC, abstractmethod
from typing import List, Dict

class EconomicProvider(ABC):
    @abstractmethod
    def get_events(self) -> List[Dict]:
        """
        Returns a list of upcoming economic events.
        Format expected: [{'event': 'NFP', 'impact': 'HIGH', 'time': datetime_obj}, ...]
        """
        pass
