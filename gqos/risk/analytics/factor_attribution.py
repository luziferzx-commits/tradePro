from decimal import Decimal
from typing import Dict
from gqos.risk.analytics.models import FactorExposureResult, FactorReturnAttributionResult

class FactorAttributionEngine:
    def calculate_attribution(self, portfolio_exposure: FactorExposureResult, factor_returns: Dict[str, Decimal], total_portfolio_return: Decimal) -> FactorReturnAttributionResult:
        """
        Decomposes the total portfolio return into factor-driven return and specific (alpha) return.
        """
        attributed_factor_returns: Dict[str, Decimal] = {}
        total_factor_return = Decimal('0')

        for factor, exposure in portfolio_exposure.exposures.items():
            f_return = factor_returns.get(factor, Decimal('0'))
            contribution = exposure * f_return
            attributed_factor_returns[factor] = contribution
            total_factor_return += contribution

        specific_return = total_portfolio_return - total_factor_return

        return FactorReturnAttributionResult(
            total_return=total_portfolio_return,
            factor_returns=attributed_factor_returns,
            specific_return=specific_return
        )
