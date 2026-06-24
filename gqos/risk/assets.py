from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AssetMetadata:
    symbol: str
    sector: str
    asset_class: str
    correlation_group: str

class AssetDirectory:
    """
    In-memory directory for looking up asset metadata.
    """
    def __init__(self):
        import threading
        self._assets = {}
        self._lock = threading.RLock()
        
    def register_asset(self, metadata: AssetMetadata) -> None:
        with self._lock:
            self._assets[metadata.symbol] = metadata
        
    def get_asset(self, symbol: str) -> Optional[AssetMetadata]:
        with self._lock:
            return self._assets.get(symbol)
