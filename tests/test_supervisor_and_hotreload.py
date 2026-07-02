"""Supervisor crash-loop guard + settings hot-reload."""
import os

from scripts import run_supervisor
from config import settings as settings_mod


def test_supervisor_stops_after_repeated_early_crashes():
    calls = {"n": 0}

    def fake_child(cmd):
        calls["n"] += 1
        return 1, 0.1  # exit code 1, ran only 0.1s = early crash

    # monkeypatch sleep to not wait
    orig_sleep = run_supervisor.time.sleep
    run_supervisor.time.sleep = lambda s: None
    try:
        rc = run_supervisor.run(cmd=["x"], run_child=fake_child)
    finally:
        run_supervisor.time.sleep = orig_sleep

    assert rc == 1
    assert calls["n"] == run_supervisor.MAX_CONSECUTIVE_CRASHES


def test_supervisor_resets_crash_count_on_healthy_run():
    seq = [ (0, 0.1), (0, 0.1), (0, 999), (0, 0.1) ]  # crash, crash, healthy, crash...
    calls = {"n": 0}

    def fake_child(cmd):
        i = calls["n"]
        calls["n"] += 1
        if i < len(seq):
            return seq[i]
        return 1, 0.1  # then keep early-crashing to eventually stop

    run_supervisor.time.sleep = lambda s: None
    rc = run_supervisor.run(cmd=["x"], run_child=fake_child)
    # Healthy run at index 2 resets the counter, so it takes >MAX more crashes to stop.
    assert rc == 1
    assert calls["n"] > run_supervisor.MAX_CONSECUTIVE_CRASHES


def test_hot_reload_applies_changed_setting(monkeypatch):
    # No-op load_dotenv so we control os.environ directly.
    monkeypatch.setattr(settings_mod, "load_dotenv", lambda **k: None)
    monkeypatch.setenv("PATTERN_PF_CEILING", "1.7")

    settings_mod.settings.PATTERN_PF_CEILING = 1.5  # current
    changes = settings_mod.reload_tunable_settings()

    assert "PATTERN_PF_CEILING" in changes
    assert settings_mod.settings.PATTERN_PF_CEILING == 1.7


def test_hot_reload_noop_when_unchanged(monkeypatch):
    monkeypatch.setattr(settings_mod, "load_dotenv", lambda **k: None)
    monkeypatch.setenv("PATTERN_PF_CEILING", "1.5")
    settings_mod.settings.PATTERN_PF_CEILING = 1.5
    changes = settings_mod.reload_tunable_settings()
    assert "PATTERN_PF_CEILING" not in changes


def test_request_restart_writes_flag(tmp_path):
    from scripts import request_restart
    flag = tmp_path / "restart.flag"
    path = request_restart.request_restart(str(flag))
    assert os.path.exists(path)
    with open(path) as f:
        assert "restart" in f.read().lower()
