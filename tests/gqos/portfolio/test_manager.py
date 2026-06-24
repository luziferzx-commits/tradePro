from decimal import Decimal
from gqos.portfolio.manager import PortfolioManager, InsufficientFundsError

def test_allocate_capital_success():
    manager = PortfolioManager("p1", Decimal('100000.0'))
    alloc = manager.allocate_capital("s1", Decimal('40000.0'))
    
    assert alloc.allocated_capital == Decimal('40000.0')
    assert alloc.buying_power == Decimal('40000.0')
    assert manager.state.unallocated_cash == Decimal('60000.0')

def test_allocate_capital_insufficient_funds():
    manager = PortfolioManager("p1", Decimal('100000.0'))
    
    try:
        manager.allocate_capital("s1", Decimal('150000.0'))
    except InsufficientFundsError:
        pass
    else:
        assert False, "Expected InsufficientFundsError"

def test_reserve_cash_success():
    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('40000.0'))
    
    success, reason = manager.reserve_cash("s1", Decimal('15000.0'))
    assert success is True
    
    alloc = manager.state.allocations["s1"]
    assert alloc.reserved_cash == Decimal('15000.0')
    assert alloc.buying_power == Decimal('25000.0')

def test_reserve_cash_over_reservation_fails():
    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('40000.0'))
    
    success, reason = manager.reserve_cash("s1", Decimal('50000.0'))
    assert success is False
    assert "Insufficient buying power" in reason
    
    alloc = manager.state.allocations["s1"]
    assert alloc.reserved_cash == Decimal('0.0')
    assert alloc.buying_power == Decimal('40000.0')

def test_release_cash_success():
    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('40000.0'))
    manager.reserve_cash("s1", Decimal('15000.0'))
    
    success, reason = manager.release_cash("s1", Decimal('15000.0'))
    assert success is True
    
    alloc = manager.state.allocations["s1"]
    assert alloc.reserved_cash == Decimal('0.0')
    assert alloc.buying_power == Decimal('40000.0')

def test_generate_snapshot():
    manager = PortfolioManager("p1", Decimal('100000.0'))
    manager.allocate_capital("s1", Decimal('40000.0'))
    manager.reserve_cash("s1", Decimal('15000.0'))
    
    snapshot = manager.generate_snapshot("s1")
    assert snapshot.total_equity == Decimal('40000.0')
    assert snapshot.buying_power == Decimal('25000.0')
    assert snapshot.available_cash == Decimal('25000.0')

if __name__ == "__main__":
    test_allocate_capital_success()
    test_allocate_capital_insufficient_funds()
    test_reserve_cash_success()
    test_reserve_cash_over_reservation_fails()
    test_release_cash_success()
    test_generate_snapshot()
    print("Portfolio Manager tests passed!")
