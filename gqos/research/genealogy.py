from typing import Dict, List, Set
from collections import defaultdict

class FeatureGenealogy:
    """
    Tracks which Alphas depend on which Features.
    Crucial for impact analysis if a bug is found in a specific feature.
    """
    def __init__(self):
        # Maps feature_name -> set of alpha_ids
        self.feature_to_alphas: Dict[str, Set[str]] = defaultdict(set)
        # Maps alpha_id -> set of feature_names
        self.alpha_to_features: Dict[str, Set[str]] = defaultdict(set)
        
    def register_alpha(self, alpha_id: str, features: List[str]):
        for feat in features:
            self.feature_to_alphas[feat].add(alpha_id)
            self.alpha_to_features[alpha_id].add(feat)
            
    def get_impacted_alphas(self, feature_name: str) -> List[str]:
        """
        Returns a list of all Alpha IDs that rely on the given feature.
        """
        return list(self.feature_to_alphas.get(feature_name, set()))
        
    def get_alpha_dependencies(self, alpha_id: str) -> List[str]:
        return list(self.alpha_to_features.get(alpha_id, set()))
