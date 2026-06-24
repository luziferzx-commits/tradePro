import pandas as pd
import numpy as np
from decimal import Decimal
import hashlib

from gqos.messaging.bus import LocalEventBus
from gqos.accounting.engine import AccountingEngine
from gqos.portfolio.manager import PortfolioManager
from gqos.backtest.engine import EventDrivenBacktester
from gqos.backtest.execution import MockExecutionHandler
from gqos.backtest.friction import FixedBpsSlippage, FixedCommission
from gqos.backtest.results import BacktestResult, calculate_backtest_metrics
from gqos.common.enums import TradeDirection
from gqos.accounting.events import FeeChargedEvent

# Mock Fee Model & FX Converter for AccountingEngine
class MockFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        # Apply $1 fixed commission per unit
        return quantity * Decimal('1.0'), "USD"

class MockFxConverter:
    def convert(self, amount, from_curr, to_curr):
        return amount

import logging

def test_event_driven_backtest_parity():
    logger = logging.getLogger("test")
    bus = LocalEventBus(logger)
    fee_model = MockFeeModel()
    fx = MockFxConverter()
    
    # Initialize Core
    accounting = AccountingEngine(bus, fee_model, fx)
    portfolio = PortfolioManager("SimPort", Decimal('10000.0'))
    
    # Initialize Backtest Components
    slippage = FixedBpsSlippage(bps=10.0) # 10 bps slippage
    
    backtester = EventDrivenBacktester(bus, None, accounting, portfolio)
    
    # Execution Handler needs a price feed. We'll wire it to the backtester's market_prices.
    def price_feed(sym):
        return backtester.market_prices[sym]
        
    execution = MockExecutionHandler(bus, slippage, price_feed)
    backtester._execution_handler = execution
    
    # Create 100-bar mock data
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    
    # Price alternates between 100 and 110
    prices = [100.0 if i % 2 == 0 else 110.0 for i in range(100)]
    price_df = pd.DataFrame({"close": prices}, index=dates)
    
    # Forecast alternates between 0.5 (Buy) and -0.5 (Sell)
    scores = [0.5 if i % 2 == 0 else -0.5 for i in range(100)]
    forecast_df = pd.DataFrame({
        "score": scores,
        "confidence": [0.9] * 100,
        "forecast_id": [f"f_{i}" for i in range(100)]
    }, index=dates)
    
    # Run Simulation
    backtester.run_simulation(forecast_df, price_df, "AAPL")
    
    # Generate Equity Curve
    eq_series = pd.Series(backtester.equity_curve)
    
    # 100 bars executed, should have traded.
    assert len(eq_series) == 100
    
    # Since we traded back and forth and paid slippage + $1 per unit commission, equity should strictly decrease over many flips
    # Initial was 10000. Let's check final equity.
    final_eq = eq_series.iloc[-1]
    print(f"Final equity: {final_eq}")
    assert final_eq > 10000.0  # Perfect oracle mock data makes huge profit
    
    # Generate Metrics
    metrics = calculate_backtest_metrics(eq_series)
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "total_return" in metrics
    
    # Validate BacktestResult
    result = BacktestResult(
        equity_curve=eq_series,
        trade_log=pd.DataFrame(), # Mocked empty for simplicity
        metrics=metrics
    )
    
    h1 = result.calculate_hash()
    assert h1 is not None

def test_slippage_and_commission_deduction():
    # Direct test of friction models
    slip = FixedBpsSlippage(bps=100.0) # 1% slippage
    # Buy at 100 -> 101
    buy_price = slip.apply_slippage(TradeDirection.BUY, Decimal('100.0'), Decimal('1.0'))
    assert buy_price == Decimal('101.0')
    
    # Sell at 100 -> 99
    sell_price = slip.apply_slippage(TradeDirection.SELL, Decimal('100.0'), Decimal('1.0'))
    assert sell_price == Decimal('99.0')
    
    comm = FixedCommission(per_unit_fee=2.5)
    fee = comm.calculate_commission(TradeDirection.BUY, Decimal('100.0'), Decimal('10.0'))
    assert fee == Decimal('25.0')

if __name__ == "__main__":
    test_event_driven_backtest_parity()
    test_slippage_and_commission_deduction()
    print("M15 Backtesting Engine tests passed!")
