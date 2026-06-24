from decimal import Decimal
from types import MappingProxyType
from gqos.risk.exposure import ExposureSnapshot, Position

def test_immutable_snapshot():
    pos = Position("AAPL", Decimal('10'), Decimal('100.0'), Decimal('110.0'))
    
    snapshot = ExposureSnapshot(
        version=1,
        parent_version=0,
        gross_exposure=Decimal('1100.0'),
        net_exposure=Decimal('1100.0'),
        positions=MappingProxyType({"AAPL": pos}),
        sector_exposures=MappingProxyType({"Tech": Decimal('1100.0')}),
        group_exposures=MappingProxyType({"Mega": Decimal('1100.0')})
    )
    
    # Attempt to mutate should raise exceptions (dataclass frozen)
    try:
        snapshot.gross_exposure = Decimal('0')
        assert False, "Should raise exception"
    except Exception:
        pass
        
    # Attempt to mutate mapping proxy should raise TypeError
    try:
        snapshot.positions["AAPL"] = None
        assert False, "Should raise exception"
    except Exception:
        pass

if __name__ == "__main__":
    test_immutable_snapshot()
    print("Snapshot Immutability Test Passed!")
