"""tests/test_symbol_registry.py"""
import os
import yaml
import pytest
from market.symbol_registry import SymbolRegistry
from market.market_metadata import MarketMetadata

@pytest.fixture
def temp_config(tmp_path):
    config_file = tmp_path / "symbols.yaml"
    data = {
        "symbols": {
            "VALID": {
                "enabled": True, "pip_size": 0.01, "tick_size": 0.01,
                "min_lot": 0.01, "max_lot": 10.0, "lot_step": 0.01,
                "liquidity_score": 0.9, "asset_class": "FOREX"
            },
            "INVALID_LOT": {
                "enabled": True, "pip_size": 0.01, "tick_size": 0.01,
                "min_lot": 1.0, "max_lot": 0.5, "lot_step": 0.01,
                "liquidity_score": 0.9
            },
            "DISABLED": {
                "enabled": False, "pip_size": 0.01, "tick_size": 0.01,
                "min_lot": 0.01, "max_lot": 10.0, "lot_step": 0.01,
                "liquidity_score": 0.9
            },
            "TF_OVERRIDE": {
                "enabled": True, "pip_size": 0.01, "tick_size": 0.01,
                "min_lot": 0.01, "max_lot": 10.0, "lot_step": 0.01,
                "liquidity_score": 0.9,
                "primary_timeframe": "H1", "context_timeframe": "D1",
                "history_bars": 1000, "context_bars": 500
            }
        }
    }
    with open(config_file, "w") as f:
        yaml.dump(data, f)
    return str(config_file)

def test_registry_load_and_validation(temp_config):
    registry = SymbolRegistry(temp_config)
    symbols = registry.get_enabled_symbols()
    
    names = [s["symbol"] for s in symbols]
    
    assert "VALID" in names
    assert "DISABLED" not in names
    assert "INVALID_LOT" not in names

def test_timeframe_override(temp_config):
    registry = SymbolRegistry(temp_config)
    
    valid = registry.get_symbol("VALID")
    assert valid["primary_timeframe"] == "M15"
    assert valid["history_bars"] == 500
    
    override = registry.get_symbol("TF_OVERRIDE")
    assert override["primary_timeframe"] == "H1"
    assert override["context_timeframe"] == "D1"
    assert override["history_bars"] == 1000
    assert override["context_bars"] == 500
