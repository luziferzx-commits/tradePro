from typing import Dict, List, Any
from decimal import Decimal
import pandas as pd

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import ExecuteTradeCommand
from gqos.common.enums import TradeDirection
from gqos.backtest.events import ForecastEvent, TargetPortfolioEvent
from gqos.accounting.events import RealizedPnLEmittedEvent, FeeChargedEvent

class EventDrivenBacktester:
    def __init__(self, event_bus: IEventBus, execution_handler: Any, accounting_engine: Any, portfolio_manager: Any):
        self._event_bus = event_bus
        self._execution_handler = execution_handler
        self._accounting = accounting_engine
        self._portfolio = portfolio_manager
        
        # Subscribe to internal events
        self._event_bus.subscribe(TargetPortfolioEvent, self._handle_target_portfolio)
        self._event_bus.subscribe(RealizedPnLEmittedEvent, self._handle_realized_pnl)
        self._event_bus.subscribe(FeeChargedEvent, self._handle_fee)
        
        self.market_prices: Dict[str, Decimal] = {}
        self.system_time: float = 0.0
        
        # Ensure strategy allocation exists
        if "global" not in self._portfolio.state.allocations:
            self._portfolio.allocate_capital("global", self._portfolio.state.unallocated_cash)
            
        # Equity curve tracking
        self.equity_curve: Dict[float, float] = {}

    def _handle_realized_pnl(self, envelope: MessageEnvelope[RealizedPnLEmittedEvent]):
        # Apply realized PnL to portfolio
        self._portfolio.apply_realized_pnl(envelope.payload.strategy_id, envelope.payload.realized_pnl)

    def _handle_fee(self, envelope: MessageEnvelope[FeeChargedEvent]):
        # Apply fee as negative PnL for simplicity
        self._portfolio.apply_realized_pnl(envelope.payload.strategy_id, -envelope.payload.amount)

    def get_total_equity(self, strategy_id: str = "global") -> Decimal:
        alloc = self._portfolio.state.allocations[strategy_id]
        equity = alloc.allocated_capital
        
        # Add unrealized PnL
        unrealized_pnl = Decimal('0')
        for pos_key, pos in self._accounting.state.positions.items():
            if pos.strategy_id == strategy_id and pos.symbol in self.market_prices:
                price = self.market_prices[pos.symbol]
                if pos.direction == TradeDirection.BUY:
                    unrealized_pnl += (price - pos.average_price) * pos.quantity
                else:
                    unrealized_pnl += (pos.average_price - price) * pos.quantity
                    
        return equity + unrealized_pnl

    def _handle_target_portfolio(self, envelope: MessageEnvelope[TargetPortfolioEvent]):
        target_weights = envelope.payload.target_weights
        
        total_equity = self.get_total_equity("global")
        if total_equity <= Decimal('0'):
            return
            
        # Minimum viable Rebalance logic
        for symbol, target_weight in target_weights.items():
            if symbol not in self.market_prices:
                continue
                
            price = self.market_prices[symbol]
            target_value = total_equity * Decimal(str(target_weight))
            target_quantity = target_value / price
            
            # Get current position
            pos_key = f"global_{symbol}"
            pos = self._accounting.state.positions.get(pos_key)
            current_quantity = pos.quantity if pos else Decimal('0')
            current_direction = pos.direction if pos else TradeDirection.BUY
            
            signed_current = current_quantity if current_direction == TradeDirection.BUY else -current_quantity
            
            quantity_diff = target_quantity - signed_current
            
            if abs(quantity_diff) < Decimal('1e-6'):
                continue
                
            direction = TradeDirection.BUY if quantity_diff > 0 else TradeDirection.SELL
            
            cmd = ExecuteTradeCommand(
                symbol=symbol,
                direction=direction,
                quantity=abs(quantity_diff),
                estimated_value=abs(quantity_diff) * price,
                strategy_id="global"
            )
            
            self._event_bus.publish(MessageEnvelope.create(
                payload=cmd,
                version=1
            ))

    def run_simulation(self, forecast_df: pd.DataFrame, price_df: pd.DataFrame, symbol: str):
        common_idx = forecast_df.index.intersection(price_df.index)
        
        for ts in common_idx:
            self.system_time = ts.timestamp() if isinstance(ts, pd.Timestamp) else float(ts)
            
            # Update market price
            current_price = Decimal(str(price_df.loc[ts, "close"]))
            self.market_prices[symbol] = current_price
            
            # Extract forecast
            row = forecast_df.loc[ts]
            score = float(row["score"])
            
            forecast_evt = ForecastEvent(
                forecast_id=str(row["forecast_id"]),
                alpha_id="sim",
                timestamp=self.system_time,
                score=score,
                confidence=float(row.get("confidence", 1.0))
            )
            self._event_bus.publish(MessageEnvelope.create(payload=forecast_evt, version=1))
            
            # Translate ForecastEvent -> TargetPortfolioEvent
            target_weights = {symbol: score}
            target_evt = TargetPortfolioEvent(
                timestamp=self.system_time,
                target_weights=target_weights
            )
            self._event_bus.publish(MessageEnvelope.create(payload=target_evt, version=1))
            
            # Snapshot equity curve at end of bar
            self.equity_curve[self.system_time] = float(self.get_total_equity("global"))
