import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

@dataclass
class PortfolioManifest:
    """
    Cryptographic footprint of the Portfolio construction.
    Ensures complete reproducibility of the allocation decisions.
    """
    portfolio_id: str
    timestamp: str
    alpha_versions: Dict[str, str]  # alpha_id -> alpha_hash
    weights: Dict[str, float]       # alpha_id -> allocated weight
    hrp_tree_hash: str              # hash of the HRP clustering tree
    kelly_fraction: float           # Kelly sizing multiplier
    regime: str                     # e.g., 'Bull_HighVol'
    validation_hash: str            # M26 Validation manifest hash

    def calculate_hash(self) -> str:
        d = asdict(self)
        # Sort everything to ensure deterministic hashing
        d['alpha_versions'] = dict(sorted(d['alpha_versions'].items()))
        d['weights'] = dict(sorted(d['weights'].items()))
        j = json.dumps(d, sort_keys=True)
        return hashlib.sha256(j.encode('utf-8')).hexdigest()
