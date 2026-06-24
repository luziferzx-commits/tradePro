from gqos.common.enums import TradeDirection
import time
from decimal import Decimal
from typing import List
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import ExecuteTradeCommand, TradeExecutedEvent
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine

def run_benchmark():
    print("=== M7C.5 Exposure Engine Benchmark ===")
    
    # 1. Setup
    directory = AssetDirectory()
    limits = ExposureLimits(
        max_gross_exposure=Decimal('100000000.0'),
        max_net_exposure=Decimal('100000000.0'),
        max_symbol_exposure=Decimal('100000000.0'),
        max_sector_exposure=Decimal('100000000.0'),
        max_correlation_group_exposure=Decimal('100000000.0')
    )
    engine = ExposureEngine(directory, limits)
    
    # 2. Pre-load 10,000 positions
    print("\nPre-loading 10,000 positions...")
    events = []
    t0 = time.perf_counter_ns()
    for i in range(10000):
        symbol = f"SYM_{i}"
        directory.register_asset(AssetMetadata(symbol, f"Sec_{i%10}", "Equity", f"Grp_{i%5}"))
        evt = TradeExecutedEvent("s1", symbol, TradeDirection.BUY, Decimal('100'), Decimal('10.0'))
        engine.apply_trade(evt)
        events.append(MessageEnvelope.create(evt, version=i+2))
    t1 = time.perf_counter_ns()
    
    # 3. apply_trade latency
    apply_latency_us = ((t1 - t0) / 10000) / 1000.0
    print(f"apply_trade() Avg Latency : {apply_latency_us:.2f} us")
    
    # 4. evaluate_trade latency (100,000 evaluations)
    print("\nRunning 100,000 evaluate_trade() calls...")
    cmd = ExecuteTradeCommand("SYM_5000", TradeDirection.BUY, Decimal('10'), Decimal('100.0'), "s1")
    t0 = time.perf_counter_ns()
    for _ in range(100000):
        engine.evaluate_trade(cmd)
    t1 = time.perf_counter_ns()
    eval_latency_us = ((t1 - t0) / 100000) / 1000.0
    print(f"evaluate_trade() Avg Latency: {eval_latency_us:.2f} us")
    
    # 5. Rebuild from events
    print("\nRebuilding from 10,000 events...")
    engine_rebuild = ExposureEngine(directory, limits)
    t0 = time.perf_counter_ns()
    engine_rebuild.rebuild_from_events(events)
    t1 = time.perf_counter_ns()
    rebuild_time_s = (t1 - t0) / 1_000_000_000.0
    print(f"rebuild_from_events() total time: {rebuild_time_s:.4f} sec")
    
    print("\nVerifying Rebuild State...")
    assert engine._snapshot.version == engine_rebuild._snapshot.version
    assert engine._snapshot.gross_exposure == engine_rebuild._snapshot.gross_exposure
    assert engine._snapshot.net_exposure == engine_rebuild._snapshot.net_exposure
    print("Rebuild State Verified: True")

if __name__ == "__main__":
    run_benchmark()
