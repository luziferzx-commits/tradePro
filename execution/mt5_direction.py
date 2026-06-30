"""Helpers for translating MT5 order/deal constants into trade direction."""

import MetaTrader5 as mt5


def position_direction_from_type(position_type: int) -> str:
    return "BUY" if position_type == mt5.POSITION_TYPE_BUY else "SELL"


def closing_deal_position_direction(deal_type: int) -> str:
    """Return the original position direction for a closing MT5 deal.

    MT5 records the closing transaction as the opposite side. A SELL deal closes
    a BUY position, and a BUY deal closes a SELL position.
    """
    return "BUY" if deal_type == mt5.DEAL_TYPE_SELL else "SELL"
