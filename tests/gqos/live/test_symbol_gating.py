"""Live symbol resolution and gating (regression locks).

Covers:
- broker-symbol alias resolution, incl. the DE30 -> DE30m base-symbol fix
- the enabled (live trading) vs simulate (learning) decoupling
"""
import yaml

from data.mt5_client import mt5_client
from market.symbol_registry import SymbolRegistry

CONFIG = "config/symbols.yaml"


def test_resolve_symbol_aliases():
    # Logical name and the stripped base name both map to the broker symbol.
    assert mt5_client.resolve_symbol("GER40") == "DE30m"
    assert mt5_client.resolve_symbol("DE30") == "DE30m"
    assert mt5_client.resolve_symbol("EURUSD") == "EURUSDm"
    # Unknown symbols pass through unchanged.
    assert mt5_client.resolve_symbol("NOPE123") == "NOPE123"


def _load_symbols():
    with open(CONFIG, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("symbols", {})


def test_disabled_symbols_still_simulate():
    symbols = _load_symbols()
    # Symbols disabled for live trading must still be simulated for learning
    # (simulate defaults to True and should not be turned off just because a
    # symbol is not traded live). XRP stays disabled for live (broker spread)
    # but must keep simulating.
    cfg = symbols.get("XRPUSD")
    assert cfg is not None, "XRPUSD missing from config"
    assert cfg.get("enabled", False) is False, "XRPUSD should be disabled for live"
    assert cfg.get("simulate", True) is not False, "XRPUSD should still simulate"


def test_live_symbols_are_subset_of_simulated():
    symbols = _load_symbols()
    live = {s for s, c in symbols.items() if c.get("enabled", False)}
    simulated = {s for s, c in symbols.items() if c.get("simulate", True)}
    assert live, "expected at least one live symbol"
    assert live <= simulated, "every live symbol must also be simulated"


def test_registry_only_loads_enabled():
    reg = SymbolRegistry(CONFIG)
    names = set(reg.symbols.keys())
    assert "XRPUSD" not in names   # disabled for live (spread)
    assert "XAUUSD" in names
