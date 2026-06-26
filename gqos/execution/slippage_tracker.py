import json
import logging
import time
from datetime import datetime
from pathlib import Path
from market.symbol_registry import SymbolRegistry
from gqos.common.enums import TradeDirection

logger = logging.getLogger(__name__)

class SlippageTracker:
    def __init__(self, log_dir="data/learning"):
        self.log_file = Path(log_dir) / "slippage_log.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.registry = SymbolRegistry("config/symbols.yaml")

    def _get_session_label(self) -> str:
        h = datetime.utcnow().hour
        if 0 <= h < 7:
            return "Asia"
        elif 7 <= h < 13:
            return "London"
        elif 13 <= h < 20:
            return "NY"
        else:
            return "Asia_Late"

    def log_slippage(self, symbol: str, direction: TradeDirection, expected_price: float, actual_price: float, execution_time_ms: float, volume: float):
        try:
            # Strip 'm' suffix if present for registry lookup
            base_symbol = symbol[:-1] if symbol.endswith('m') else symbol
            sym_config = self.registry.get_symbol(base_symbol) or {}
            
            pip_size = sym_config.get('pip_size', 0.0001)
            tick_size = sym_config.get('tick_size', 0.00001)
            tick_value = sym_config.get('tick_value', 1.0)
            contract_size = sym_config.get('contract_size', 100000.0)
            
            # Calculate slippage in points
            if direction == TradeDirection.BUY:
                # If BUY, actual > expected is BAD (positive slippage means cost)
                slippage_points = actual_price - expected_price
            else:
                # If SELL, actual < expected is BAD
                slippage_points = expected_price - actual_price
                
            # Convert to pips
            slippage_pips = slippage_points / pip_size if pip_size > 0 else 0
            
            # Calculate USD cost
            # Note: volume in MT5 is typically in lots, and tick_value is per tick_size per lot.
            # cost = (slippage_points / tick_size) * tick_value * volume
            if tick_size > 0:
                slippage_usd = (slippage_points / tick_size) * tick_value * float(volume)
            else:
                slippage_usd = 0.0
                
            entry_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "session": self._get_session_label(),
                "symbol": symbol,
                "direction": direction.name,
                "volume": volume,
                "expected_entry": expected_price,
                "actual_entry": actual_price,
                "slippage_pips": slippage_pips,
                "slippage_usd": slippage_usd,
                "execution_time_ms": execution_time_ms
            }
            
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry_data) + "\n")
                
            logger.info(f"[SlippageTracker] {symbol} {direction.name}: {slippage_pips:.2f} pips slippage (${slippage_usd:.2f}) in {execution_time_ms:.1f}ms")
            
        except Exception as e:
            logger.error(f"[SlippageTracker] Failed to log slippage: {e}")

slippage_tracker = SlippageTracker()
