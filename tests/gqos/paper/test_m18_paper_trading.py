import pandas as pd
import numpy as np
import time
from decimal import Decimal

from gqos.messaging.bus import LocalEventBus
from gqos.accounting.engine import AccountingEngine
from gqos.portfolio.manager import PortfolioManager
from gqos.backtest.friction import FixedBpsSlippage

from gqos.paper.events import MarketDataEvent, BarClosedEvent, FeatureDriftEvent
from gqos.paper.adapter import SimulatedLiveFeed
from gqos.paper.execution import PaperExecutionHandler
from gqos.paper.attribution import DailyAttributionEngine
from gqos.paper.monitor import RealTimeDriftMonitor
from gqos.paper.engine import PaperTradingEngine

class MockFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        return Decimal('0'), "USD"

class MockFxConverter:
    def convert(self, amount, from_curr, to_curr):
        return amount

def test_paper_trading_async_flow():
    bus = LocalEventBus(None) # Muted logger
    
    accounting = AccountingEngine(bus, MockFeeModel(), MockFxConverter())
    portfolio = PortfolioManager("PaperPort", Decimal("10000.0"))
    
    slippage = FixedBpsSlippage(bps=10.0) # 0.1%
    exec_handler = PaperExecutionHandler(bus, slippage)
    
    attribution = DailyAttributionEngine(bus)
    monitor = RealTimeDriftMonitor(bus)
    
    # Set a strict drift boundary
    monitor.set_boundary("feature_x", mean=0.0, std_dev=1.0, threshold=2.0)
    
    # Track drift events
    drift_events = []
    bus.subscribe(FeatureDriftEvent, lambda env: drift_events.append(env.payload))
    
    def dummy_forecast(symbol: str, bar_data: pd.Series) -> float:
        # Simple alternating forecast
        return 1.0 if bar_data["close"] % 2 == 0 else -1.0

    engine = PaperTradingEngine(bus, accounting, portfolio, dummy_forecast)
    
    # Create 10 bars
    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    data = pd.DataFrame({
        "open": np.arange(100, 110),
        "high": np.arange(101, 111),
        "low": np.arange(99, 109),
        "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        "feature_x": [0.0, 0.5, 1.0, 2.5, 0.0, -0.5, 3.0, 0.0, 0.0, 0.0] # 2.5 and 3.0 will trigger drift
    }, index=dates)
    
    feed = SimulatedLiveFeed(bus, data, symbol="BTCUSD", interval_ms=10)
    
    # Start the async feed
    feed.start()
    
    # Wait for the feed to finish (10 bars * 10ms = 100ms + buffer)
    time.sleep(0.5)
    
    feed.stop()
    
    # Verifications
    # 1. Drift events should have fired without halting execution
    assert len(drift_events) == 2
    assert drift_events[0].actual_value == 2.5
    assert drift_events[1].actual_value == 3.0
    
    # 2. Orders were queued and filled
    # Since we traded back and forth, accounting should have processed fills
    assert len(accounting.state.positions) > 0 or len(accounting.state.transactions) > 0
    assert len(exec_handler._order_queue) == 1 # The last order generated at the very last bar remains pending until a next tick arrives!
    
    # 3. Attribution
    # Trigger EOD attribution
    total_equity = engine._get_total_equity("global")
    total_pnl = float(total_equity) - 10000.0
    attr_evt = attribution.generate_daily_attribution("2023-01-10", total_pnl)
    
    assert attr_evt.total_pnl == total_pnl
    assert attr_evt.friction_cost > 0.0
    assert attr_evt.alpha_pnl == total_pnl + attr_evt.friction_cost

if __name__ == "__main__":
    test_paper_trading_async_flow()
    print("M18 Paper Trading tests passed!")
