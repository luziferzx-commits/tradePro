"""Import smoke test.

Many modules are imported lazily inside try/except blocks in production
(e.g. mt5_adapter -> recovery_readiness, outcome_logger -> post_trade_review),
so a broken or untracked module fails silently at runtime instead of loudly.
Importing them explicitly here — with MetaTrader5 mocked by conftest — turns
that class of failure into a hard CI error, and confirms the package imports
cleanly on Linux without the Windows-only MT5 wheel.
"""
import importlib

import pytest

CRITICAL_MODULES = [
    # Core engine / messaging / execution
    "gqos.messaging.bus",
    "gqos.execution.stages",
    "gqos.live.engine",
    "gqos.live.oms",
    "gqos.live.adapters.mt5_adapter",
    # Risk / sizing / accounting
    "gqos.risk.exposure_engine",
    "gqos.risk.portfolio_budget",
    "gqos.sizing.policies",
    "gqos.accounting.engine",
    # Learning / ops modules that are imported lazily with swallowed errors
    "gqos.learning.outcome_logger",
    "gqos.learning.session_analyzer",
    "gqos.learning.post_trade_review",
    "gqos.ops.recovery_readiness",
    "gqos.ops.spread_guard",
    "gqos.ops.spread_regime_memory",
    "gqos.ops.pa_filter_calibrator",
    "gqos.ops.learning_health",
    # Config
    "config.settings",
]


@pytest.mark.parametrize("module_name", CRITICAL_MODULES)
def test_module_imports(module_name):
    assert importlib.import_module(module_name) is not None
