from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class PortfolioSnapshot:
    """
    An immutable snapshot of the portfolio's current state.
    Used by Sizing Policies to determine available capital.
    """
    total_equity: Decimal
    available_cash: Decimal
    margin_used: Decimal
    buying_power: Decimal
    unrealized_pnl: Decimal

    @classmethod
    def create_mock(cls, capital: Decimal) -> 'PortfolioSnapshot':
        """Helper to create a simple mock portfolio for testing."""
        return cls(
            total_equity=capital,
            available_cash=capital,
            margin_used=Decimal('0'),
            buying_power=capital,
            unrealized_pnl=Decimal('0')
        )
