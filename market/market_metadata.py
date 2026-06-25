"""market/market_metadata.py"""
from typing import Optional
from market.symbol_registry import SymbolRegistry

class MarketMetadata:
    def __init__(self, registry: SymbolRegistry):
        self.registry = registry

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().upper()

    def get_asset_class(self, symbol: str) -> str:
        meta = self.registry.get_symbol(self.normalize_symbol(symbol))
        return meta["asset_class"] if meta else "UNKNOWN"

    def convert_points_to_pips(self, symbol: str, points: float) -> float:
        meta = self.registry.get_symbol(self.normalize_symbol(symbol))
        if not meta: return points
        # points * tick_size / pip_size
        return points * meta["tick_size"] / meta["pip_size"]

    def get_spread_limit(self, symbol: str) -> int:
        meta = self.registry.get_symbol(self.normalize_symbol(symbol))
        return meta.get("max_spread_points", 99999) if meta else 99999
        
    def get_volatility_multiplier(self, symbol: str) -> float:
        meta = self.registry.get_symbol(self.normalize_symbol(symbol))
        return meta.get("volatility_multiplier", 1.0) if meta else 1.0

    def get_liquidity_score(self, symbol: str) -> float:
        meta = self.registry.get_symbol(self.normalize_symbol(symbol))
        return meta.get("liquidity_score", 0.0) if meta else 0.0
