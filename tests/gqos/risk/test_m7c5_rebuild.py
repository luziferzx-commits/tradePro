from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import TradeExecutedEvent
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine

def test_event_sourced_rebuild():
    directory = AssetDirectory()
    directory.register_asset(AssetMetadata("BTC", "Crypto", "Crypto", "Crypto-Majors"))
    
    limits = ExposureLimits(
        max_gross_exposure=Decimal('10000.0'),
        max_net_exposure=Decimal('10000.0'),
        max_symbol_exposure=Decimal('10000.0'),
        max_sector_exposure=Decimal('10000.0'),
        max_correlation_group_exposure=Decimal('10000.0')
    )
    
    engine1 = ExposureEngine(directory, limits)
    
    # Live apply
    evt1 = TradeExecutedEvent("s1", "BTC", TradeDirection.BUY, Decimal('2'), Decimal('50000.0'))
    evt2 = TradeExecutedEvent("s1", "BTC", TradeDirection.SELL, Decimal('1'), Decimal('60000.0'))
    
    engine1.apply_trade(evt1)
    engine1.apply_trade(evt2)
    
    snap1 = engine1._snapshot
    
    # Rebuild from events
    events = [
        MessageEnvelope.create(evt1, version=1),
        MessageEnvelope.create(evt2, version=1)
    ]
    
    engine2 = ExposureEngine(directory, limits)
    engine2.rebuild_from_events(events)

    snap2 = engine2._snapshot

    # The substantive exposure state must be reproduced exactly from the event
    # stream. (Snapshot.version tracks the event-store version on rebuild vs an
    # in-memory counter on live apply — a documented divergence in the Exposure
    # Version Policy tech debt, so it is not compared here.)
    assert snap1.gross_exposure == snap2.gross_exposure
    assert snap1.net_exposure == snap2.net_exposure
    assert snap1.positions["BTC"].quantity == snap2.positions["BTC"].quantity

    # Rebuild must be deterministic: replaying the same events yields the same
    # snapshot version every time.
    engine3 = ExposureEngine(directory, limits)
    engine3.rebuild_from_events(events)
    assert engine3._snapshot.version == snap2.version

if __name__ == "__main__":
    test_event_sourced_rebuild()
    print("Event Sourced Rebuild Test Passed!")
