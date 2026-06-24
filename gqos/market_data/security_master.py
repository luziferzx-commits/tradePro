from abc import ABC, abstractmethod
from typing import Dict

class ISecurityMaster(ABC):
    @abstractmethod
    def get_sector(self, symbol: str) -> str:
        pass

class MockSecurityMaster(ISecurityMaster):
    def __init__(self, mappings: Dict[str, str] = None):
        self.mappings = mappings or {}
        
    def get_sector(self, symbol: str) -> str:
        return self.mappings.get(symbol, "UNCLASSIFIED")
