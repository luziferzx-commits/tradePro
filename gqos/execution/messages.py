from dataclasses import dataclass
from gqos.messaging.contracts import Command, Event
from gqos.domain.models.execution import Trade
from gqos.domain.models.intelligence import Decision

@dataclass(frozen=True)
class ExecuteTradeCommand(Command):
    decision: Decision

@dataclass(frozen=True)
class TradeExecutedEvent(Event):
    trade: Trade
