import pandas as pd
from typing import Callable, Any, Dict
from decimal import Decimal

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.paper.events import BarClosedEvent, MarketDataEvent
from gqos.backtest.events import ForecastEvent, TargetPortfolioEvent
from gqos.accounting.events import RealizedPnLEmittedEvent, FeeChargedEvent
from gqos.risk.events import ExecuteTradeCommand
from gqos.common.enums import TradeDirection
import uuid

class PaperTradingEngine:
    """
    Orchestrates live/paper trading by reacting to market events rather than looping.
    """
    def __init__(self, event_bus: IEventBus, accounting_engine: Any, portfolio_manager: Any, forecast_callback: Callable[[str, pd.Series], float]):
        self._event_bus = event_bus
        self._accounting = accounting_engine
        self._portfolio = portfolio_manager
        self._forecast_callback = forecast_callback
        
        self.market_prices: Dict[str, Decimal] = {}
        
        # Subscribe to market events
        self._event_bus.subscribe(MarketDataEvent, self._handle_market_data)
        self._event_bus.subscribe(BarClosedEvent, self._handle_bar_closed)
        
        # Subscribe to internal lifecycle events
        self._event_bus.subscribe(TargetPortfolioEvent, self._handle_target_portfolio)
        self._event_bus.subscribe(RealizedPnLEmittedEvent, self._handle_realized_pnl)
        self._event_bus.subscribe(FeeChargedEvent, self._handle_fee)
        
        if "global" not in self._portfolio.state.allocations:
            self._portfolio.allocate_capital("global", self._portfolio.state.unallocated_cash)

    def _handle_market_data(self, envelope: MessageEnvelope[MarketDataEvent]):
        tick = envelope.payload
        self.market_prices[tick.symbol] = Decimal(str(tick.price))

    def _handle_bar_closed(self, envelope: MessageEnvelope[BarClosedEvent]):
        event = envelope.payload
        
        # 1. Generate Forecast
        score = self._forecast_callback(event.symbol, event.bar_data)
        
        forecast_evt = ForecastEvent(
            forecast_id=str(uuid.uuid4()),
            alpha_id="paper_sim",
            timestamp=event.timestamp,
            score=score,
            confidence=1.0
        )
        self._event_bus.publish(MessageEnvelope.create(payload=forecast_evt, version=1))
        
        # 2. Translate to TargetPortfolio (Simplistic 1-asset mapper)
        target_weights = {event.symbol: score}
        target_evt = TargetPortfolioEvent(
            timestamp=event.timestamp,
            target_weights=target_weights
        )
        self._event_bus.publish(MessageEnvelope.create(payload=target_evt, version=1))

    def _handle_target_portfolio(self, envelope: MessageEnvelope[TargetPortfolioEvent]):
        target_weights = envelope.payload.target_weights
        total_equity = self._get_total_equity("global")
        if total_equity <= Decimal('0'):
            return
            
        for symbol, target_weight in target_weights.items():
            if symbol not in self.market_prices:
                continue
                
            price = self.market_prices[symbol]
            target_value = total_equity * Decimal(str(target_weight))
            target_quantity = target_value / price
            
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
            
            self._event_bus.publish(MessageEnvelope.create(payload=cmd, version=1))

    def _get_total_equity(self, strategy_id: str) -> Decimal:
        alloc = self._portfolio.state.allocations[strategy_id]
        equity = alloc.allocated_capital
        
        unrealized_pnl = Decimal('0')
        for pos_key, pos in self._accounting.state.positions.items():
            if pos.strategy_id == strategy_id and pos.symbol in self.market_prices:
                price = self.market_prices[pos.symbol]
                if pos.direction == TradeDirection.BUY:
                    unrealized_pnl += (price - pos.average_price) * pos.quantity
                else:
                    unrealized_pnl += (pos.average_price - price) * pos.quantity
        return equity + unrealized_pnl

    def _handle_realized_pnl(self, envelope: MessageEnvelope[RealizedPnLEmittedEvent]):
        self._portfolio.apply_realized_pnl(envelope.payload.strategy_id, envelope.payload.realized_pnl)

    def _handle_fee(self, envelope: MessageEnvelope[FeeChargedEvent]):
        self._portfolio.apply_realized_pnl(envelope.payload.strategy_id, -envelope.payload.amount)
