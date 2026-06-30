from decimal import Decimal
from types import SimpleNamespace

from gqos.common.enums import TradeDirection
from gqos.execution.pipeline import PipelineContext
from gqos.execution.stages import AccountLossGuardStage
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import ExecuteTradeCommand, TradeRejectedByCircuitBreaker
from gqos.sizing.events import SizePositionCommand


class FakeMT5:
    def __init__(self, balance, equity=None):
        self._account = SimpleNamespace(
            balance=float(balance),
            equity=float(equity if equity is not None else balance),
        )

    def account_info(self):
        return self._account


def test_account_loss_guard_blocks_new_sizing_when_realized_drawdown_breaches_limit():
    stage = AccountLossGuardStage(
        reference_balance=Decimal("10000"),
        max_realized_drawdown_pct=Decimal("0.10"),
        max_equity_drawdown_pct=Decimal("0.12"),
        mt5_module=FakeMT5(balance=Decimal("8973.29"), equity=Decimal("9043.61")),
        emit_structured_logs=False,
    )
    cmd = SizePositionCommand("gqos_alpha_v1", "XAUUSDm", TradeDirection.BUY, Decimal("4040"))

    result = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())

    assert not result.continue_pipeline
    assert result.reason == "Account loss guard tripped"
    assert isinstance(result.emitted_events[0], TradeRejectedByCircuitBreaker)
    assert "Realized drawdown" in result.emitted_events[0].reason


def test_account_loss_guard_blocks_execute_command_when_equity_drawdown_breaches_limit():
    stage = AccountLossGuardStage(
        reference_balance=Decimal("10000"),
        max_realized_drawdown_pct=Decimal("0.10"),
        max_equity_drawdown_pct=Decimal("0.12"),
        mt5_module=FakeMT5(balance=Decimal("9200"), equity=Decimal("8700")),
        emit_structured_logs=False,
    )
    cmd = ExecuteTradeCommand(
        symbol="XAUUSDm",
        direction=TradeDirection.BUY,
        quantity=Decimal("0.01"),
        estimated_value=Decimal("1000"),
        strategy_id="gqos_alpha_v1",
    )

    result = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())

    assert not result.continue_pipeline
    assert isinstance(result.emitted_events[0], TradeRejectedByCircuitBreaker)
    assert "Equity drawdown" in result.emitted_events[0].reason


def test_account_loss_guard_allows_new_entries_inside_limits():
    stage = AccountLossGuardStage(
        reference_balance=Decimal("10000"),
        max_realized_drawdown_pct=Decimal("0.10"),
        max_equity_drawdown_pct=Decimal("0.12"),
        mt5_module=FakeMT5(balance=Decimal("9600"), equity=Decimal("9550")),
        emit_structured_logs=False,
    )
    cmd = SizePositionCommand("gqos_alpha_v1", "EURUSDm", TradeDirection.SELL, Decimal("1.08"))
    env = MessageEnvelope.create(cmd, version=1)

    result = stage.process(env, PipelineContext())

    assert result.continue_pipeline
    assert result.envelope is env
    assert result.emitted_events == []
