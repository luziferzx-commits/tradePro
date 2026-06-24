from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any

class AlphaState(Enum):
    CANDIDATE = "candidate"     # In Factory / Research
    CHALLENGER = "challenger"   # Auto-promoted from Factory, runs in Shadow Routing
    CHAMPION = "champion"       # Manually approved for live capital
    WATCHLIST = "watchlist"     # Degrading performance, capital decaying
    RETIRED = "retired"         # 0 capital, but still tracked
    GRAVEYARD = "graveyard"     # Deleted / ignored completely

@dataclass
class AlphaLifecycleEntry:
    alpha_id: str
    current_state: AlphaState
    history: list # list of dicts: {"from": state, "to": state, "reason": str, "timestamp": str}
    
class AlphaLifecycleManager:
    def __init__(self):
        self.alphas: Dict[str, AlphaLifecycleEntry] = {}
        
    def register_candidate(self, alpha_id: str):
        if alpha_id not in self.alphas:
            self.alphas[alpha_id] = AlphaLifecycleEntry(
                alpha_id=alpha_id,
                current_state=AlphaState.CANDIDATE,
                history=[]
            )
            
    def transition(self, alpha_id: str, new_state: AlphaState, reason: str, timestamp: str):
        if alpha_id not in self.alphas:
            raise ValueError(f"Unknown alpha {alpha_id}")
            
        entry = self.alphas[alpha_id]
        entry.history.append({
            "from": entry.current_state.value,
            "to": new_state.value,
            "reason": reason,
            "timestamp": timestamp
        })
        entry.current_state = new_state
