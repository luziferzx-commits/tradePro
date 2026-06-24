from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Mapping
import time

# Deep copy helper for immutable tree
def _deep_freeze(d: Mapping[str, Any]) -> Mapping[str, Any]:
    from types import MappingProxyType
    frozen = {}
    for k, v in d.items():
        if isinstance(v, dict):
            frozen[k] = _deep_freeze(v)
        else:
            frozen[k] = v
    return MappingProxyType(frozen)

@dataclass(frozen=True)
class StateSnapshot:
    """
    Immutable tree representation of the system state at a point in time.
    """
    version: int
    timestamp: float
    data: Mapping[str, Any]
    metadata: Mapping[str, Any]
    parent_version: Optional[int] = None
    
    def diff(self, other: 'StateSnapshot') -> Dict[str, Any]:
        """
        Compare this snapshot with another snapshot and return the changed keys.
        Returns a dictionary of {key: (old_value, new_value)}.
        Currently performs a shallow diff at the top level for performance.
        """
        changes = {}
        all_keys = set(self.data.keys()).union(set(other.data.keys()))
        
        for k in all_keys:
            val_self = self.data.get(k)
            val_other = other.data.get(k)
            if val_self != val_other:
                changes[k] = (val_self, val_other)
                
        return changes
    
    @classmethod
    def create(cls, version: int, data: Dict[str, Any], metadata: Dict[str, Any], parent_version: Optional[int] = None) -> 'StateSnapshot':
        """
        Safely constructs a frozen snapshot by freezing the underlying dictionaries.
        """
        return cls(
            version=version,
            timestamp=time.time(),
            data=_deep_freeze(data),
            metadata=_deep_freeze(metadata),
            parent_version=parent_version
        )
