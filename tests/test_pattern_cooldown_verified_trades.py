import json
from datetime import datetime


def test_cooldown_self_heal_ignores_unfilled_signal_approvals(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data" / "learning"
    data_dir.mkdir(parents=True)

    state_file = data_dir / "pattern_cooldown.json"
    state_file.write_text(
        json.dumps({"PD_unfilled": datetime.utcnow().isoformat()}),
        encoding="utf-8",
    )
    (data_dir / "system_events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "SIGNAL_APPROVED",
                "pattern_id": "PD_unfilled",
                "ts": datetime.utcnow().isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "pending_trades.json").write_text(
        json.dumps(
            {
                "GQOS-1": {
                    "pattern_id": "PD_pending_no_ticket",
                    "open_time": datetime.utcnow().isoformat(),
                },
                "12345": {
                    "pattern_id": "PD_filled",
                    "ticket": 12345,
                    "open_time": datetime.utcnow().isoformat(),
                },
            }
        ),
        encoding="utf-8",
    )

    from strategy.cooldown_manager import PatternCooldownManager

    manager = PatternCooldownManager(cooldown_hours=6.0, state_file=str(state_file))

    assert not manager.check_cooldown("PD_unfilled")
    assert not manager.check_cooldown("PD_pending_no_ticket")
    assert manager.check_cooldown("PD_filled")
