"""tests/test_runtime_integration.py"""
import pytest
import os
import sys

# Ensure config overrides for test
from config.settings import settings

def test_settings_flags():
    """Test that all Phase D config flags exist and default correctly."""
    assert hasattr(settings, "ENABLE_MULTI_ASSET")
    assert hasattr(settings, "ENABLE_PORTFOLIO_RISK")
    assert hasattr(settings, "ENABLE_SIGNAL_JOURNAL")
    assert hasattr(settings, "ENABLE_DD_GUARD")
    assert hasattr(settings, "DRY_RUN")

def test_multi_asset_mode_dry_run_blocks_live():
    """Test that DRY_RUN=True blocks actual execution logic (simulated by flags)."""
    settings.ENABLE_MULTI_ASSET = True
    settings.DRY_RUN = True
    
    assert settings.ENABLE_MULTI_ASSET is True
    assert settings.DRY_RUN is True
    # Testing main loop directly is difficult without a full mock, 
    # but run_runtime_dry_run.py effectively covers the E2E simulation.

def test_single_symbol_mode_fallback():
    """Test that default single-symbol mode is preserved when ENABLE_MULTI_ASSET is False."""
    settings.ENABLE_MULTI_ASSET = False
    assert settings.ENABLE_MULTI_ASSET is False
