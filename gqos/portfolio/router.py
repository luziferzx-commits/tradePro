from typing import Dict
from gqos.portfolio.lifecycle import AlphaState, AlphaLifecycleManager

class ShadowRouter:
    """
    Routes Alpha capital allocations based on their Lifecycle State.
    Challengers trade in Shadow Ledger (0.0 live capital).
    Champions get live capital.
    Watchlist/Retired get capital decays.
    """
    def __init__(self, lifecycle_manager: AlphaLifecycleManager):
        self.lifecycle_manager = lifecycle_manager
        
    def route_allocations(self, target_allocations: Dict[str, float]) -> Dict[str, float]:
        routed = {}
        
        for alpha_id, target_cap in target_allocations.items():
            if alpha_id not in self.lifecycle_manager.alphas:
                routed[alpha_id] = 0.0
                continue
                
            state = self.lifecycle_manager.alphas[alpha_id].current_state
            
            if state == AlphaState.CHAMPION:
                routed[alpha_id] = target_cap
            elif state == AlphaState.CHALLENGER:
                routed[alpha_id] = 0.0 # Shadow trading only
            elif state == AlphaState.WATCHLIST:
                routed[alpha_id] = target_cap * 0.5 # Example immediate half cut
            elif state == AlphaState.RETIRED or state == AlphaState.GRAVEYARD:
                routed[alpha_id] = 0.0
            else:
                routed[alpha_id] = 0.0
                
        return routed
