from typing import Dict, Any, Optional

class ChampionChallengerRegistry:
    def __init__(self):
        self.champions: Dict[str, str] = {} # strategy_id -> alpha_id
        self.challengers: Dict[str, Dict[str, Any]] = {} # alpha_id -> metadata
        self.promotion_history: list = []
        
    def register_challenger(self, alpha_id: str, strategy_id: str, metadata: Dict[str, Any]):
        self.challengers[alpha_id] = {
            "strategy_id": strategy_id,
            "metadata": metadata
        }
        
    def promote_to_champion(self, alpha_id: str, reason: str):
        if alpha_id not in self.challengers:
            raise ValueError(f"Alpha {alpha_id} is not registered as a challenger.")
            
        strategy_id = self.challengers[alpha_id]["strategy_id"]
        previous_champion = self.champions.get(strategy_id)
        
        self.champions[strategy_id] = alpha_id
        self.promotion_history.append({
            "strategy_id": strategy_id,
            "previous_champion": previous_champion,
            "new_champion": alpha_id,
            "reason": reason
        })
        
    def get_champion(self, strategy_id: str) -> Optional[str]:
        return self.champions.get(strategy_id)
