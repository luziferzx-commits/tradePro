from decimal import Decimal
from gqos.sizing.models import SizingRequest, SizingResult
from gqos.sizing.policies import ISizingPolicy
from gqos.sizing.portfolio import PortfolioSnapshot

class PositionSizingEngine:
    """
    Core engine for calculating position sizes based on Quant policies.
    """
    
    def size_trade(self, request: SizingRequest, policy: ISizingPolicy, portfolio: PortfolioSnapshot) -> SizingResult:
        """
        Pure function to calculate the sizing result based on a request and policy.
        Raises InvalidSizingRequestError on failure.
        """
        if portfolio.total_equity <= Decimal('0'):
            raise ValueError("Available equity is zero or negative.")
            
        return policy.calculate_size(request, portfolio)
