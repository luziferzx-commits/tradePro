import json

from gqos.learning import outcome_logger as outcome_module
from gqos.learning.outcome_logger import TradeOutcomeLogger


def test_outcome_logger_returns_record_when_closing_by_ticket(tmp_path, monkeypatch):
    monkeypatch.setattr(outcome_module, "PENDING_PATH", str(tmp_path / "pending.json"))
    monkeypatch.setattr(outcome_module, "OUTCOMES_PATH", str(tmp_path / "outcomes.jsonl"))
    logger = TradeOutcomeLogger(emit_structured_logs=False)

    logger.register_intent(
        decision_id="D1",
        symbol="XAUUSDm",
        direction="BUY",
        entry_price=100.0,
        sl_price=99.0,
        tp_price=102.0,
        pattern_id="P1",
        pattern_pf=1.2,
        pattern_sim=0.8,
        session="London",
        strategy_id="s1",
        source="LIVE",
        run_id="run-1",
        account_id="acct-1",
    )
    logger.on_trade_opened(ticket=12345, decision_id="D1")

    record = logger.on_trade_closed(ticket=12345, exit_price=101.0, realized_pnl=50.0)

    assert record["decision_id"] == "D1"
    assert record["ticket"] == 12345
    assert record["outcome"] == "WIN"
    assert record["source"] == "LIVE"
    assert record["run_id"] == "run-1"
    assert record["account_id"] == "acct-1"


def test_outcome_logger_can_close_oldest_ticket_linked_trade_by_symbol(tmp_path, monkeypatch):
    monkeypatch.setattr(outcome_module, "PENDING_PATH", str(tmp_path / "pending.json"))
    monkeypatch.setattr(outcome_module, "OUTCOMES_PATH", str(tmp_path / "outcomes.jsonl"))
    logger = TradeOutcomeLogger(emit_structured_logs=False)

    for decision_id, ticket in [("D1", 111), ("D2", 222)]:
        logger.register_intent(
            decision_id=decision_id,
            symbol="USDJPYm",
            direction="SELL",
            entry_price=150.0,
            sl_price=151.0,
            tp_price=148.0,
            pattern_id=f"P-{decision_id}",
            pattern_pf=1.2,
            pattern_sim=0.8,
            session="NY",
            strategy_id="s1",
        )
        logger.on_trade_opened(ticket=ticket, decision_id=decision_id)

    record = logger.on_trade_closed_by_symbol("USDJPYm", exit_price=149.0, realized_pnl=25.0)

    assert record["decision_id"] == "D1"
    assert record["ticket"] == 111
    outcomes = (tmp_path / "outcomes.jsonl").read_text().strip().splitlines()
    assert json.loads(outcomes[0])["decision_id"] == "D1"


def test_outcome_logger_uses_broker_tick_value_for_actual_r(tmp_path, monkeypatch):
    monkeypatch.setattr(outcome_module, "PENDING_PATH", str(tmp_path / "pending.json"))
    monkeypatch.setattr(outcome_module, "OUTCOMES_PATH", str(tmp_path / "outcomes.jsonl"))
    logger = TradeOutcomeLogger(emit_structured_logs=False)

    logger.register_intent(
        decision_id="D1",
        symbol="EURUSDm",
        direction="SELL",
        entry_price=1.13999,
        sl_price=1.14346,
        tp_price=1.13800,
        pattern_id="P1",
        pattern_pf=1.2,
        pattern_sim=0.8,
        session="London",
        strategy_id="s1",
    )
    logger.on_trade_opened(
        ticket=3394517543,
        decision_id="D1",
        volume=0.03,
        fill_price=1.13999,
        stop_loss_price=1.14346,
        tick_size=0.00001,
        tick_value=1.0,
    )

    record = logger.on_trade_closed(ticket=3394517543, exit_price=1.13953, realized_pnl=1.38)

    assert record["actual_r"] == 0.133


def test_outcome_logger_recovers_pending_trade_from_fill_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(outcome_module, "PENDING_PATH", str(tmp_path / "pending.json"))
    monkeypatch.setattr(outcome_module, "OUTCOMES_PATH", str(tmp_path / "outcomes.jsonl"))
    logger = TradeOutcomeLogger(emit_structured_logs=False)

    recovered = logger.on_trade_opened(
        ticket=3395667527,
        decision_id="MISSING_DECISION",
        symbol="EURUSDm",
        direction="BUY",
        volume=0.01,
        fill_price=1.14204,
        stop_loss_price=1.13767,
        take_profit_price=1.15000,
        tick_size=0.00001,
        tick_value=1.0,
    )

    assert recovered is not None
    assert recovered["ticket"] == 3395667527

    record = logger.on_trade_closed(
        ticket=3395667527,
        exit_price=1.14186,
        realized_pnl=-0.18,
    )

    assert record["actual_r"] == -0.041
