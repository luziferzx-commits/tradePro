"""LiveSessionGuard auto-reset: daily pause clears when the block window rolls over."""
from types import SimpleNamespace

from gqos.ops import live_guard
from gqos.ops.live_guard import LiveSessionGuard
from gqos.risk.engine import CircuitBreakerEngine


def _guard():
    aw = SimpleNamespace(is_paused=True, guard_probe_reason="daily loss")
    cb = CircuitBreakerEngine()
    g = LiveSessionGuard(alpha_worker=aw, circuit_breaker=cb)
    g.circuit_breaker.trip("DAILY_LOSS_LIMIT", "loss")
    return g, aw, cb


def test_reevaluate_resumes_when_block_cleared(monkeypatch):
    g, aw, cb = _guard()
    monkeypatch.setattr(live_guard.mt5, "account_info", lambda: SimpleNamespace(balance=10000.0))
    monkeypatch.setattr(live_guard, "get_entry_block_reason", lambda balance: None)  # all clear (new day)

    msg = g.reevaluate()

    assert msg and "resuming" in msg.lower()
    assert aw.is_paused is False
    assert cb.is_tripped("DAILY_LOSS_LIMIT") is False


def test_reevaluate_stays_paused_while_blocked(monkeypatch):
    g, aw, cb = _guard()
    monkeypatch.setattr(live_guard.mt5, "account_info", lambda: SimpleNamespace(balance=10000.0))
    monkeypatch.setattr(live_guard, "get_entry_block_reason", lambda balance: "Daily-loss guard active: ...")

    assert g.reevaluate() is None
    assert aw.is_paused is True  # still blocked


def test_reevaluate_noop_when_not_guarded(monkeypatch):
    aw = SimpleNamespace(is_paused=False, guard_probe_reason="")
    g = LiveSessionGuard(alpha_worker=aw, circuit_breaker=CircuitBreakerEngine())
    # Should short-circuit before touching MT5.
    monkeypatch.setattr(live_guard.mt5, "account_info", lambda: (_ for _ in ()).throw(AssertionError("should not be called")))
    assert g.reevaluate() is None
