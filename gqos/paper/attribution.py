import pandas as pd
from typing import List
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import TradeExecutedEvent
from gqos.paper.events import DailyAttributionEvent

class DailyAttributionEngine:
    def __init__(self, event_bus: IEventBus):
        self._event_bus = event_bus
        self._trades: List[TradeExecutedEvent] = []
        
        # We listen to TradeExecutedEvent to accumulate friction costs
        self._event_bus.subscribe(TradeExecutedEvent, self._handle_trade)
        
    def _handle_trade(self, envelope: MessageEnvelope[TradeExecutedEvent]):
        self._trades.append(envelope.payload)
        
    def generate_daily_attribution(self, date: str, total_pnl: float) -> DailyAttributionEvent:
        """
        Called externally (e.g. by PaperTradingEngine at end of day)
        """
        friction_cost = sum([float(t.slippage_amount) for t in self._trades])
        # We could also track commissions if we listened to FeeChargedEvent
        
        alpha_pnl = total_pnl + friction_cost # Since total_pnl is net, alpha is gross
        
        event = DailyAttributionEvent(
            date=date,
            total_pnl=total_pnl,
            alpha_pnl=alpha_pnl,
            friction_cost=friction_cost
        )
        
        self._event_bus.publish(MessageEnvelope.create(payload=event, version=1))
        
        # Clear trades for the next day
        self._trades.clear()
        
        return event
