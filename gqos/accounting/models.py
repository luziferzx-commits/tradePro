from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict
from gqos.common.enums import TradeDirection

@dataclass
class Position:
    strategy_id: str
    symbol: str
    direction: TradeDirection
    quantity: Decimal
    average_price: Decimal
    realized_pnl: Decimal = Decimal('0')

@dataclass
class CashAccount:
    strategy_id: str
    currency: str
    balance: Decimal

@dataclass
class AccountingState:
    strategy_id: str
    cash: Dict[str, CashAccount] = field(default_factory=dict)
    positions: Dict[str, Position] = field(default_factory=dict)
