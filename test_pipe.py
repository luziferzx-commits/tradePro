import logging
logging.basicConfig(level=logging.INFO)

from market.symbol_registry import SymbolRegistry
from gqos.portfolio.core import Portfolio
from gqos.portfolio.sizing import SizingEngine, RiskPolicy
from gqos.execution.stages import (
    Pipeline,
    PortfolioSnapshotStage,
    SizingStage,
    CircuitBreakerStage,
    ExposureStage,
    RiskBudgetStage,
    PortfolioReservationStage,
    ExecutionStage
)
from gqos.execution.commands import SizePositionCommand
from gqos.execution.command_bus import CommandBus
from gqos.execution.exposure import ExposureEngine
from gqos.risk.circuit_breaker import CircuitBreakerEngine
from gqos.risk.risk_engine import RiskEngine
from decimal import Decimal
from data.mt5_client import MT5Client

registry = SymbolRegistry("config/symbols.yaml")
mt5_client = MT5Client()
portfolio = Portfolio()
sizing_engine = SizingEngine(registry)
policy = RiskPolicy(max_risk_per_trade_pct=0.02)
cb_engine = CircuitBreakerEngine()
exposure = ExposureEngine(mt5_client)
risk_engine = RiskEngine()

pipeline = Pipeline([
    PortfolioSnapshotStage(portfolio),
    SizingStage(sizing_engine, policy),
    CircuitBreakerStage(cb_engine),
    ExposureStage(exposure, max_positions=10, max_portfolio_risk_pct=0.20),
    RiskBudgetStage(risk_engine),
    PortfolioReservationStage(portfolio)
])

# Test placing a GBPUSD BUY
cmd = SizePositionCommand(
    strategy_id="test",
    symbol="GBPUSDm",
    direction=True, # Enum, but True is usually BUY. Let's use TradeDirection
)
# Wait, TradeDirection enum is needed
from gqos.execution.commands import TradeDirection
cmd = SizePositionCommand(
    strategy_id="test",
    symbol="GBPUSDm",
    direction=TradeDirection.BUY,
    entry_price=Decimal("1.25"),
    stop_loss_price=Decimal("1.24"),
    take_profit_price=Decimal("1.26"),
    conviction=Decimal("0.8")
)

context = pipeline.execute(cmd)
print(f"Result: {context.status}, Halt Reason: {context.halt_reason}")
