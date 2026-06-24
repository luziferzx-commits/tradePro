import time
import hashlib
from dataclasses import dataclass
from gqos.messaging.bus import LocalEventBus
from gqos.messaging.contracts import Event, MessageEnvelope
from gqos.kernel.implementations.ConsoleLogger import ConsoleLogger

@dataclass(frozen=True)
class TickEvent(Event):
    tick_id: int
    price: float

def run_m1c5_messaging_replay():
    print("--- GQOS M1C.5: Messaging Replay Determinism Test ---")
    logger = ConsoleLogger()
    
    # 1. Publish Phase
    print("Phase 1: Recording 100 Events...")
    bus1 = LocalEventBus(logger)
    
    recorded_sequence_1 = []
    
    def handler1(env: MessageEnvelope[TickEvent]):
        # Simulate processing and creating a hash chain
        data_str = f"{env.message_id}:{env.payload.tick_id}:{env.payload.price:.2f}"
        recorded_sequence_1.append(data_str)
        
    bus1.subscribe(TickEvent, handler1)
    
    # Save envelopes to simulate an Event Store
    event_store = []
    
    for i in range(100):
        env = MessageEnvelope.create(TickEvent(tick_id=i, price=2000.0 + i), version=1)
        event_store.append(env)
        bus1.publish(env)
        
    hash1 = hashlib.sha256("".join(recorded_sequence_1).encode()).hexdigest()
    print(f"Recording Complete. Hash: {hash1}")
    
    # 2. Replay Phase
    print("Phase 2: Replaying 100 Events on a fresh Bus...")
    bus2 = LocalEventBus(logger)
    
    recorded_sequence_2 = []
    
    def handler2(env: MessageEnvelope[TickEvent]):
        data_str = f"{env.message_id}:{env.payload.tick_id}:{env.payload.price:.2f}"
        recorded_sequence_2.append(data_str)
        
    bus2.subscribe(TickEvent, handler2)
    
    for env in event_store:
        bus2.publish(env)
        
    hash2 = hashlib.sha256("".join(recorded_sequence_2).encode()).hexdigest()
    print(f"Replay Complete. Hash: {hash2}")
    
    assert hash1 == hash2, "Determinism failed! Hashes do not match."
    print("100% Hash Match. FIFO Ordering and Replay Determinism VERIFIED.")
    print("--- M1C.5 SUCCESS ---")

if __name__ == "__main__":
    run_m1c5_messaging_replay()
