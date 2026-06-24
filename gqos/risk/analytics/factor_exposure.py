from decimal import Decimal
from typing import List, Dict
from gqos.accounting.models import Position
from gqos.common.enums import TradeDirection
from gqos.risk.analytics.models import FactorExposureResult
from gqos.risk.analytics.factor_model import IFactorModel

class FactorExposureEngine:
    def calculate_portfolio_exposure(self, positions: List[Position], factor_model: IFactorModel) -> FactorExposureResult:
        """
        Calculates the net portfolio exposure to each factor.
        Portfolio Factor Exposure = Sum over i (Weight_i * Exposure_{i, factor})
        """
        if not positions:
            return FactorExposureResult({})

        # Calculate Total Market Value
        total_market_value = sum((pos.quantity * pos.average_price) for pos in positions)
        if total_market_value == Decimal('0'):
            return FactorExposureResult({})

        portfolio_exposures: Dict[str, Decimal] = {}

        for pos in positions:
            market_value = pos.quantity * pos.average_price
            weight = market_value / total_market_value
            
            # If short, weight is effectively negative for exposure contribution
            if pos.direction == TradeDirection.SELL:
                weight = -weight

            symbol_exposures = factor_model.get_factor_exposures(pos.symbol)
            
            for factor, exposure in symbol_exposures.items():
                portfolio_exposures[factor] = portfolio_exposures.get(factor, Decimal('0')) + (weight * exposure)

        return FactorExposureResult(portfolio_exposures)
