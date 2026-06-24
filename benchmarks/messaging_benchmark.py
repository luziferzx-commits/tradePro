import time
from dataclasses import dataclass
from gqos.messaging.bus import LocalEventBus, LocalCommandBus
from gqos.messaging.contracts import Event, Command, MessageEnvelope
from gqos.kernel.implementations.ConsoleLogger import ConsoleLogger

@dataclass(frozen=True)
class BenchEvent(Event):
    value: int

@dataclass(frozen=True)
class BenchCommand(Command):
    value: int

def run_messaging_benchmark():
    print("--- GQOS Messaging Benchmark ---")
    logger = ConsoleLogger()
    event_bus = LocalEventBus(logger)
    cmd_bus = LocalCommandBus(logger)
    
    iterations = 100_000
    
    # 1. Registration Benchmark
    start_time = time.perf_counter()
    def dummy_handler(env): pass
    for _ in range(100):
        event_bus.subscribe(BenchEvent, dummy_handler)
    end_time = time.perf_counter()
    reg_us = ((end_time - start_time) / 100) * 1_000_000
    print(f"Registration Time: {reg_us:.4f} us per subscribe")
    assert reg_us < 50.0, f"Registration time {reg_us:.4f} exceeds 50 us budget"
    
    # Reset subscribers
    event_bus = LocalEventBus(logger)
    
    # 2. Publish (1 Subscriber)
    def single_handler(env): pass
    event_bus.subscribe(BenchEvent, single_handler)
    
    env = MessageEnvelope.create(BenchEvent(1), version=1)
    
    start_time = time.perf_counter()
    for _ in range(iterations):
        event_bus.publish(env)
    end_time = time.perf_counter()
    
    pub_us = ((end_time - start_time) / iterations) * 1_000_000
    print(f"Publish Time (1 sub): {pub_us:.4f} us per publish")
    assert pub_us < 10.0, f"Publish time {pub_us:.4f} exceeds 10 us budget"
    
    # 3. Publish (100 Subscribers)
    event_bus = LocalEventBus(logger)
    for _ in range(100):
        def multi_handler(env): pass
        event_bus.subscribe(BenchEvent, multi_handler)
        
    start_time = time.perf_counter()
    for _ in range(iterations):
        event_bus.publish(env)
    end_time = time.perf_counter()
    
    pub_100_us = ((end_time - start_time) / iterations) * 1_000_000
    print(f"Publish Time (100 subs): {pub_100_us:.4f} us per publish")
    assert pub_100_us < 200.0, f"Publish time 100 subs {pub_100_us:.4f} exceeds 200 us budget"
    
    # 4. Command Dispatch
    def cmd_handler(env): return True
    cmd_bus.register_handler(BenchCommand, cmd_handler)
    
    cmd_env = MessageEnvelope.create(BenchCommand(1), version=1)
    
    start_time = time.perf_counter()
    for _ in range(iterations):
        cmd_bus.dispatch(cmd_env)
    end_time = time.perf_counter()
    
    cmd_us = ((end_time - start_time) / iterations) * 1_000_000
    print(f"Command Dispatch Time: {cmd_us:.4f} us per dispatch")
    assert cmd_us < 10.0, f"Command time {cmd_us:.4f} exceeds 10 us budget"
    
    print("--- Benchmark SUCCESS ---")

if __name__ == "__main__":
    run_messaging_benchmark()
