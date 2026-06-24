from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class IHypothesis:
    """
    Research Hypothesis Registry.
    Tracks the core idea behind the Alpha, answering *why* it should make money.
    """
    hypothesis_id: str
    name: str
    category: str # e.g., 'Mean Reversion', 'Trend', 'Carry'
    expected_edge: str # Description of the expected edge
    market: str
    asset_class: str
    regime_tags: List[str] # e.g., ['Trending', 'High Vol']
    created_by: str
    created_date: str
    status: str # 'Active', 'Rejected', 'Proven'
    
    def __post_init__(self):
        if not self.created_date:
            self.created_date = datetime.utcnow().isoformat()
