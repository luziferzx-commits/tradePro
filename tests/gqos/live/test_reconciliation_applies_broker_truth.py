from decimal import Decimal

from gqos.common.enums import TradeDirection
from gqos.live.engine import LiveTradingEngine
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.messaging.contracts import Command, Event, MessageEnvelope
from gqos.portfolio.manager import PortfolioManager
from gqos.accounting.engine import AccountingEngine
from gqos.accounting.models import Position


class MockCommandBus(ICommandBus):
    def register_handler(self, command_type, handler) -> None:
        self.handler = handler

    def dispatch(self, envelope: MessageEnvelope[Command]):
        return self.handler(envelope)


class MockEventBus(IEventBus):
    def __init__(self):
        self.published_events = []

    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        self.published_events.append(envelope.payload)

    def subscribe(self, event_type, handler) -> None:
        pass

    def unsubscribe(self, event_type, handler) -> None:
        pass


class MockAdapter:
    def __init__(self, positions):
        self.positions = positions

    def get_actual_positions(self):
        return {
            symbol: details["quantity"] if isinstance(details, dict) else details
            for symbol, details in self.positions.items()
        }

    def get_actual_position_details(self):
        return {
            symbol: (
                details
                if isinstance(details, dict)
                else {"quantity": details, "average_price": Decimal("0")}
            )
            for symbol, details in self.positions.items()
        }

    def stop(self):
        pass


class MockPersistence:
    def load_snapshot(self, accounting_state, portfolio_state):
        return False

    def save_snapshot(self, accounting_state, portfolio_state):
        pass


class MockSafety:
    def __init__(self):
        self.triggered = False

    def trigger(self, reason):
        self.triggered = True

    def check_new_order_allowed(self):
        return True


class MockFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        return Decimal("0"), "USD"


class MockFxConverter:
    def convert(self, amount, from_curr, to_curr):
        return amount


def make_engine(adapter_positions, halt_on_reconcile_mismatch=False):
    bus = MockEventBus()
    cmd_bus = MockCommandBus()
    accounting = AccountingEngine(bus, MockFeeModel(), MockFxConverter())
    portfolio = PortfolioManager("LivePort", Decimal("100000.0"))
    portfolio.allocate_capital("gqos_alpha_v1", Decimal("100000.0"))
    safety = MockSafety()
    engine = LiveTradingEngine(
        bus,
        cmd_bus,
        oms=None,
        adapter=MockAdapter(adapter_positions),
        safety=safety,
        persistence=MockPersistence(),
        accounting=accounting,
        portfolio=portfolio,
        halt_on_reconcile_mismatch=halt_on_reconcile_mismatch,
    )
    return engine, accounting, portfolio, safety


def test_reconciliation_creates_missing_broker_position_in_accounting():
    engine, accounting, portfolio, _safety = make_engine({
        "XAUUSDm": {"quantity": Decimal("0.03"), "average_price": Decimal("3300.0")}
    })

    engine.start()

    pos = accounting.state.positions["gqos_alpha_v1_XAUUSDm"]
    assert pos.symbol == "XAUUSDm"
    assert pos.direction == TradeDirection.BUY
    assert pos.quantity == Decimal("0.03")
    assert pos.average_price == Decimal("3300.0")
    assert portfolio.state.allocations["gqos_alpha_v1"].reserved_cash == Decimal("99.000")
    assert engine.is_reconciled is True


def test_reconciliation_removes_stale_local_position_absent_from_broker():
    engine, accounting, portfolio, _safety = make_engine({})
    accounting.state.positions["gqos_alpha_v1_XAUUSDm"] = Position(
        strategy_id="gqos_alpha_v1",
        symbol="XAUUSDm",
        direction=TradeDirection.BUY,
        quantity=Decimal("0.03"),
        average_price=Decimal("1900.0"),
    )

    engine.start()

    assert accounting.state.positions == {}
    assert engine.is_reconciled is True


def test_reconciliation_halts_when_flag_enabled():
    # Opt-in safety: with halt enabled, a mismatch still syncs broker truth into
    # the ledger but blocks trading (is_reconciled=False) and trips the kill
    # switch for manual review.
    engine, accounting, portfolio, safety = make_engine(
        {"XAUUSDm": {"quantity": Decimal("0.03"), "average_price": Decimal("3300.0")}},
        halt_on_reconcile_mismatch=True,
    )

    engine.start()

    pos = accounting.state.positions["gqos_alpha_v1_XAUUSDm"]
    assert pos.quantity == Decimal("0.03")  # broker truth still applied
    assert engine.is_reconciled is False
    assert safety.triggered is True
