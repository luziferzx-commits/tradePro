"""tests/test_multi_asset_scanner.py"""
import pytest
from market.symbol_registry import SymbolRegistry
from market.market_metadata import MarketMetadata
from scanner.multi_asset_scanner import MultiAssetScanner
from scanner.opportunity_ranker import OpportunityRanker

class MockRegistry:
    def get_enabled_symbols(self):
        return [
            {"symbol": "GOOD", "max_spread_points": 20, "liquidity_score": 1.0},
            {"symbol": "BAD_DATA", "max_spread_points": 20, "liquidity_score": 1.0}
        ]

class MockMetadata:
    def get_spread_limit(self, symbol): return 20
    def get_liquidity_score(self, symbol): return 1.0

class MockScanner(MultiAssetScanner):
    def _scan_single_symbol(self, symbol, meta):
        if symbol == "BAD_DATA":
            raise ValueError("Simulated network failure")
        return {
            'timestamp': '2026-06-25',
            'symbol': symbol,
            'side': 'BUY',
            'model_probability': 0.8,
            'expected_r': 2.0,
            'spread_points': 10,
            'volatility_regime': 'NORMAL'
        }

def test_scanner_skips_bad_symbol():
    registry = MockRegistry()
    metadata = MockMetadata()
    scanner = MockScanner(registry, metadata)
    
    approved, rejected = scanner.scan_all()
    
    assert len(approved) == 1
    assert approved[0]["symbol"] == "GOOD"
    
    assert len(rejected) == 1
    assert rejected[0]["symbol"] == "BAD_DATA"
    assert "Scan Exception" in rejected[0]["reason"]

def test_ranker_rejects_bad_signals():
    metadata = MockMetadata()
    signals = [
        {"symbol": "S1", "model_probability": 0.3, "expected_r": 2.0, "spread_points": 10, "volatility_regime": "NORMAL"}, # Low prob
        {"symbol": "S2", "model_probability": 0.8, "expected_r": -1.0, "spread_points": 10, "volatility_regime": "NORMAL"}, # Bad R
        {"symbol": "S3", "model_probability": 0.8, "expected_r": 2.0, "spread_points": 50, "volatility_regime": "NORMAL"}, # High spread
        {"symbol": "S4", "model_probability": 0.8, "expected_r": 2.0, "spread_points": 10, "volatility_regime": "EXTREME"}, # Extreme vol
        {"symbol": "S5", "model_probability": 0.8, "expected_r": 2.0, "spread_points": 10, "volatility_regime": "NORMAL"}, # Good
    ]
    
    approved, rejected = OpportunityRanker.rank_and_filter(signals, metadata)
    
    assert len(approved) == 1
    assert approved[0]["symbol"] == "S5"
    
    assert len(rejected) == 4
    reject_reasons = [r["reason"] for r in rejected]
    assert any("probability" in r for r in reject_reasons)
    assert any("Expected R" in r for r in reject_reasons)
    assert any("Spread" in r for r in reject_reasons)
    assert any("Extreme" in r for r in reject_reasons)
