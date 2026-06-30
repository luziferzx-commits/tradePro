from decimal import Decimal
from types import SimpleNamespace

from gqos.common.enums import TradeDirection
from gqos.execution.pipeline import PipelineContext
from gqos.execution import stages
from gqos.execution.stages import ExposureStage, TradeThrottleStage
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.events import ExecuteTradeCommand, TradeRejectedByCircuitBreaker, TradeRejectedByExposureLimit
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine
from gqos.sizing.events import SizePositionCommand


def test_trade_throttle_blocks_symbol_after_hourly_limit():
    now = [1000.0]
    stage = TradeThrottleStage(
        max_global_per_hour=10,
        max_symbol_per_hour=1,
        clock=lambda: now[0],
        emit_structured_logs=False,
    )
    cmd = SizePositionCommand("s1", "XAUUSDm", TradeDirection.BUY, Decimal("100"))

    first = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())
    second = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())

    assert first.continue_pipeline
    assert not second.continue_pipeline
    assert isinstance(second.emitted_events[0], TradeRejectedByCircuitBreaker)

    now[0] += 3601
    third = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())
    assert third.continue_pipeline


def test_trade_throttle_releases_no_fill_slot():
    stage = TradeThrottleStage(
        max_global_per_hour=1,
        max_symbol_per_hour=1,
        clock=lambda: 1000.0,
        emit_structured_logs=False,
    )
    cmd = SizePositionCommand("s1", "NZDUSDm", TradeDirection.SELL, Decimal("100"))

    first = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())
    blocked = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())
    released = stage.release_for_symbol("NZDUSDm", "broker rejected without fill")
    retry = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())

    assert first.continue_pipeline
    assert not blocked.continue_pipeline
    assert released
    assert retry.continue_pipeline


def test_exposure_stage_blocks_correlation_group_cap(monkeypatch):
    monkeypatch.setattr(
        stages.mt5,
        "account_info",
        lambda: SimpleNamespace(balance=10000.0),
    )
    monkeypatch.setattr(
        stages.mt5,
        "positions_get",
        lambda: [
            SimpleNamespace(symbol="XAUUSDm", sl=0.0, price_open=2000.0, volume=0.01),
            SimpleNamespace(symbol="XAGUSDm", sl=0.0, price_open=25.0, volume=0.01),
        ],
    )

    asset_dir = AssetDirectory()
    asset_dir.register_asset(AssetMetadata("XAUUSDm", "Metals", "CFD", "METALS"))
    exposure = ExposureEngine(
        asset_dir,
        ExposureLimits(
            max_gross_exposure=Decimal("1000000"),
            max_net_exposure=Decimal("1000000"),
            max_symbol_exposure=Decimal("1000000"),
            max_sector_exposure=Decimal("1000000"),
            max_correlation_group_exposure=Decimal("1000000"),
        ),
    )
    stage = ExposureStage(
        exposure,
        max_positions=20,
        max_portfolio_risk_pct=0.08,
        max_correlated_positions_per_group=2,
    )
    cmd = ExecuteTradeCommand(
        symbol="XAUUSDm",
        direction=TradeDirection.BUY,
        quantity=Decimal("0.01"),
        estimated_value=Decimal("100"),
        strategy_id="s1",
    )

    result = stage.process(MessageEnvelope.create(cmd, version=1), PipelineContext())

    assert not result.continue_pipeline
    assert isinstance(result.emitted_events[0], TradeRejectedByExposureLimit)
    assert result.emitted_events[0].limit_type == "CORRELATION_GROUP"
