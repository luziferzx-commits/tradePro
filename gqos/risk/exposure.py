from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Mapping
from types import MappingProxyType
import time
from gqos.risk.assets import AssetDirectory

@dataclass(frozen=True)
class ExposureLimits:
    max_gross_exposure: Decimal
    max_net_exposure: Decimal
    max_symbol_exposure: Decimal
    max_sector_exposure: Decimal
    max_correlation_group_exposure: Decimal

@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    last_price: Decimal
    
    @property
    def net_value(self) -> Decimal:
        return self.quantity * self.last_price
        
    @property
    def gross_value(self) -> Decimal:
        return abs(self.net_value)

@dataclass(frozen=True)
class ExposureSnapshot:
    """
    Immutable snapshot of exposure state.
    """
    version: int
    parent_version: int
    timestamp: float = field(default_factory=time.time)
    
    gross_exposure: Decimal = Decimal('0')
    net_exposure: Decimal = Decimal('0')
    
    positions: Mapping[str, Position] = field(default_factory=lambda: MappingProxyType({}))
    sector_exposures: Mapping[str, Decimal] = field(default_factory=lambda: MappingProxyType({}))
    group_exposures: Mapping[str, Decimal] = field(default_factory=lambda: MappingProxyType({}))
    
    def get_symbol_gross(self, symbol: str) -> Decimal:
        pos = self.positions.get(symbol)
        return pos.gross_value if pos else Decimal('0')
        
    def get_sector_gross(self, sector: str) -> Decimal:
        return self.sector_exposures.get(sector, Decimal('0'))
        
    def get_group_gross(self, group: str) -> Decimal:
        return self.group_exposures.get(group, Decimal('0'))
        
    def __hash__(self):
        # M7C.5 Technical Debt: Snapshot Hash
        return hash((
            self.version,
            self.gross_exposure,
            self.net_exposure,
            frozenset(self.positions.items()),
            frozenset(self.sector_exposures.items()),
            frozenset(self.group_exposures.items())
        ))
        
    @property
    def snapshot_id(self) -> str:
        return f"snap_v{self.version}_{abs(hash(self))}"
