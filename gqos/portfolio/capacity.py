from typing import Dict
from dataclasses import dataclass

@dataclass
class CapacityEntry:
    max_capacity: float
    used_capacity: float
    
    @property
    def remaining_capacity(self) -> float:
        return max(0.0, self.max_capacity - self.used_capacity)

class AlphaCapacityTracker:
    """
    Tracks institutional capital capacity per Alpha to prevent scaling beyond market limits.
    """
    def __init__(self):
        self.capacities: Dict[str, CapacityEntry] = {}
        
    def set_max_capacity(self, alpha_id: str, max_cap: float):
        if alpha_id not in self.capacities:
            self.capacities[alpha_id] = CapacityEntry(max_capacity=max_cap, used_capacity=0.0)
        else:
            self.capacities[alpha_id].max_capacity = max_cap
            
    def update_usage(self, alpha_id: str, used: float):
        if alpha_id in self.capacities:
            self.capacities[alpha_id].used_capacity = used
            
    def can_allocate(self, alpha_id: str, requested_amount: float) -> bool:
        if alpha_id not in self.capacities:
            return True # Unconstrained
        return self.capacities[alpha_id].remaining_capacity >= requested_amount
