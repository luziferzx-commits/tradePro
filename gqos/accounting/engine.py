from decimal import Decimal
from typing import List, Optional
from gqos.messaging.contracts import MessageEnvelope, Event
from gqos.messaging.bus import IEventBus
from gqos.common.enums import TradeDirection
from gqos.risk.events import TradeExecutedEvent
from gqos.accounting.models import AccountingState, Position, CashAccount
from gqos.accounting.events import (
    PositionOpenedEvent, PositionAdjustedEvent, PositionClosedEvent,
    RealizedPnLEmittedEvent, FeeChargedEvent
)
from gqos.accounting.fee_model import IFeeModel
from gqos.accounting.fx import IFxConverter

class AccountingEngine:
    def __init__(self, event_bus: IEventBus, fee_model: IFeeModel, fx_converter: IFxConverter, base_currency: str = "USD"):
        self._event_bus = event_bus
        self._fee_model = fee_model
        self._fx = fx_converter
        self._base_currency = base_currency
        self.state = AccountingState(strategy_id="global") # For single-engine simplicity or dict of states
        
        self._event_bus.subscribe(TradeExecutedEvent, self._handle_trade_executed)
        
    def _handle_trade_executed(self, envelope: MessageEnvelope[TradeExecutedEvent]):
        trade = envelope.payload
        events = self.process_trade(trade)
        
        for event in events:
            # Apply locally
            self.apply_event(event)
            # Publish for others (like PortfolioManager)
            self._event_bus.publish(MessageEnvelope.create(
                event,
                version=envelope.version,
                correlation_id=envelope.correlation_id
            ))
            
    def process_trade(self, trade: TradeExecutedEvent) -> List[Event]:
        events = []
        
        # 1. Fee Calculation
        fee_amount, fee_currency = self._fee_model.calculate_fee(
            symbol=trade.symbol,
            direction=trade.direction,
            quantity=trade.quantity,
            execution_price=trade.execution_price
        )
        
        if fee_amount > Decimal('0'):
            events.append(FeeChargedEvent(
                strategy_id=trade.strategy_id,
                amount=fee_amount,
                currency=fee_currency,
                reason="Trade Execution Fee"
            ))
            
        # 2. Position Accounting
        pos_key = f"{trade.strategy_id}_{trade.symbol}"
        pos = self.state.positions.get(pos_key)
        
        if pos is None or pos.quantity == Decimal('0'):
            # Open new position
            events.append(PositionOpenedEvent(
                strategy_id=trade.strategy_id,
                symbol=trade.symbol,
                direction=trade.direction,
                quantity=trade.quantity,
                average_price=trade.execution_price,
                ticket=trade.ticket
            ))
            return events
            
        if pos.direction == trade.direction:
            # Add to existing position (Average Cost)
            new_quantity = pos.quantity + trade.quantity
            new_avg_price = ((pos.quantity * pos.average_price) + (trade.quantity * trade.execution_price)) / new_quantity
            
            events.append(PositionAdjustedEvent(
                strategy_id=trade.strategy_id,
                symbol=trade.symbol,
                direction=pos.direction,
                new_quantity=new_quantity,
                new_average_price=new_avg_price,
                quantity_changed=trade.quantity
            ))
            return events
            
        # Opposite direction (Closing / Flipping)
        if trade.quantity <= pos.quantity:
            # Partial or Full Close
            realized_pnl = self._calculate_realized_pnl(
                pos.direction, trade.quantity, pos.average_price, trade.execution_price
            )
            
            events.append(PositionClosedEvent(
                strategy_id=trade.strategy_id,
                symbol=trade.symbol,
                direction=pos.direction,
                quantity_closed=trade.quantity,
                exit_price=trade.execution_price,
                ticket=trade.ticket
            ))
            
            if realized_pnl != Decimal('0'):
                events.append(RealizedPnLEmittedEvent(
                    strategy_id=trade.strategy_id,
                    symbol=trade.symbol,
                    realized_pnl=realized_pnl,
                    ticket=trade.ticket,
                    exit_price=trade.execution_price,
                    direction=pos.direction.name
                ))
                
            if trade.quantity < pos.quantity:
                events.append(PositionAdjustedEvent(
                    strategy_id=trade.strategy_id,
                    symbol=trade.symbol,
                    direction=pos.direction,
                    new_quantity=pos.quantity - trade.quantity,
                    new_average_price=pos.average_price, # Average price doesn't change on close
                    quantity_changed=-trade.quantity
                ))
                
            return events
            
        # Flip (Trade quantity > Position quantity)
        closed_qty = pos.quantity
        realized_pnl = self._calculate_realized_pnl(
            pos.direction, closed_qty, pos.average_price, trade.execution_price
        )
        
        events.append(PositionClosedEvent(
            strategy_id=trade.strategy_id,
            symbol=trade.symbol,
            direction=pos.direction,
            quantity_closed=closed_qty,
            exit_price=trade.execution_price,
            ticket=trade.ticket
        ))
        
        if realized_pnl != Decimal('0'):
            events.append(RealizedPnLEmittedEvent(
                strategy_id=trade.strategy_id,
                symbol=trade.symbol,
                realized_pnl=realized_pnl,
                ticket=trade.ticket,
                exit_price=trade.execution_price,
                direction=pos.direction.name
            ))
            
        opened_qty = trade.quantity - closed_qty
        events.append(PositionOpenedEvent(
            strategy_id=trade.strategy_id,
            symbol=trade.symbol,
            direction=trade.direction,
            quantity=opened_qty,
            average_price=trade.execution_price,
            ticket=trade.ticket
        ))
        
        return events

    def _calculate_realized_pnl(self, position_direction: TradeDirection, closed_qty: Decimal, entry_price: Decimal, exit_price: Decimal) -> Decimal:
        if position_direction == TradeDirection.BUY:
            return (exit_price - entry_price) * closed_qty
        else:
            return (entry_price - exit_price) * closed_qty

    def apply_event(self, event: Event):
        if isinstance(event, PositionOpenedEvent):
            pos_key = f"{event.strategy_id}_{event.symbol}"
            self.state.positions[pos_key] = Position(
                strategy_id=event.strategy_id,
                symbol=event.symbol,
                direction=event.direction,
                quantity=event.quantity,
                average_price=event.average_price
            )
        elif isinstance(event, PositionAdjustedEvent):
            pos_key = f"{event.strategy_id}_{event.symbol}"
            pos = self.state.positions[pos_key]
            pos.quantity = event.new_quantity
            pos.average_price = event.new_average_price
        elif isinstance(event, PositionClosedEvent):
            pos_key = f"{event.strategy_id}_{event.symbol}"
            pos = self.state.positions[pos_key]
            if pos.quantity == event.quantity_closed:
                del self.state.positions[pos_key]
        elif isinstance(event, RealizedPnLEmittedEvent):
            # The engine doesn't update its own localized cash with PnL, PortfolioManager handles Equity.
            # But we could track realized PnL per position here if we wanted.
            pass
        elif isinstance(event, FeeChargedEvent):
            cash_key = f"{event.strategy_id}_{event.currency}"
            if cash_key not in self.state.cash:
                self.state.cash[cash_key] = CashAccount(strategy_id=event.strategy_id, currency=event.currency, balance=Decimal('0'))
            self.state.cash[cash_key].balance -= event.amount
