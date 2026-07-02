"""market/symbol_registry.py"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)

class SymbolRegistry:
    def __init__(self, config_path: str = "config/symbols.yaml"):
        self.config_path = config_path
        self.symbols = {}
        self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            logger.error(f"Symbol config not found: {self.config_path}")
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "symbols" not in data:
            logger.error("Invalid YAML format: missing 'symbols' root key.")
            return

        for symbol, meta in data["symbols"].items():
            if not meta.get("enabled", False):
                continue
            
            if self._validate(symbol, meta):
                # Set defaults for timeframe override
                meta.setdefault("primary_timeframe", "M15")
                meta.setdefault("context_timeframe", "H4")
                meta.setdefault("history_bars", 500)
                meta.setdefault("context_bars", 300)
                meta["symbol"] = symbol
                self.symbols[symbol] = meta
            else:
                logger.warning(f"Symbol {symbol} failed validation and will be skipped.")

    def _validate(self, symbol: str, meta: dict) -> bool:
        try:
            if meta.get("pip_size", 0) <= 0: return False
            if meta.get("tick_size", 0) <= 0: return False
            if meta.get("min_lot", 0) <= 0: return False
            if meta.get("lot_step", 0) <= 0: return False
            if meta.get("max_lot", 0) < meta.get("min_lot", 0): return False
            
            lq = meta.get("liquidity_score", 0)
            if not (0.0 <= lq <= 1.0): return False
            
            return True
        except Exception as e:
            logger.error(f"Validation error for {symbol}: {e}")
            return False

    def get_enabled_symbols(self) -> list[dict]:
        return list(self.symbols.values())
        
    def get_symbol(self, symbol: str) -> dict:
        return self.symbols.get(symbol)
