"""portfolio/exposure_manager.py"""
from market.market_metadata import MarketMetadata

class ExposureManager:
    def __init__(self, metadata: MarketMetadata, max_total_risk_pct: float = 0.03, max_asset_class_risk_pct: float = 0.02):
        self.metadata = metadata
        self.max_total_risk_pct = max_total_risk_pct
        self.max_asset_class_risk_pct = max_asset_class_risk_pct
        
    def check_exposure_limits(self, candidate_symbol: str, candidate_risk_pct: float, open_positions: list[dict]) -> tuple[bool, str]:
        """
        Checks if adding this candidate trade violates any exposure limits.
        """
        asset_class = self.metadata.get_asset_class(candidate_symbol)
        
        total_risk = 0.0
        class_risk = 0.0
        
        for pos in open_positions:
            risk = pos.get('risk_amount_pct', 0.0) # Risk as a percentage of account
            total_risk += risk
            
            pos_class = self.metadata.get_asset_class(pos.get('symbol', ''))
            if pos_class == asset_class:
                class_risk += risk
                
        if total_risk + candidate_risk_pct > self.max_total_risk_pct:
            return False, f"Exceeds max total risk ({total_risk + candidate_risk_pct:.2%} > {self.max_total_risk_pct:.2%})"
            
        if class_risk + candidate_risk_pct > self.max_asset_class_risk_pct:
            return False, f"Exceeds max {asset_class} risk ({class_risk + candidate_risk_pct:.2%} > {self.max_asset_class_risk_pct:.2%})"
            
        return True, "OK"
