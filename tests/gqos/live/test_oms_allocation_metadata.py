from decimal import Decimal

from gqos.common.enums import TradeDirection
from gqos.live.events import OrderUpdateEvent
from gqos.live.oms import OrderManagementSystem
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import Event, MessageEnvelope


class MockEventBus(IEventBus):
    def __init__(self):
        self.published_events = []

    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        self.published_events.append(envelope.payload)

    def subscribe(self, event_type, handler) -> None:
        pass

    def unsubscribe(self, event_type, handler) -> None:
        pass


def test_oms_order_updates_carry_allocation_ids():
    bus = MockEventBus()
    oms = OrderManagementSystem(bus)

    order_id = oms.create_order(
        "XAUUSD",
        TradeDirection.BUY,
        Decimal("0.01"),
        "s1",
        risk_allocation_id="risk-1",
        portfolio_allocation_id="cash-1",
    )

    update = bus.published_events[-1]
    assert isinstance(update, OrderUpdateEvent)
    assert update.order_id == order_id
    assert update.risk_allocation_id == "risk-1"
    assert update.portfolio_allocation_id == "cash-1"
