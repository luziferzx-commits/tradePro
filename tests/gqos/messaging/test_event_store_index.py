import unittest
from gqos.messaging.store import InMemoryEventStore
from gqos.messaging.contracts import MessageEnvelope, Event
from dataclasses import dataclass

@dataclass(frozen=True)
class DummyEvent(Event):
    value: int

class TestEventStoreIndex(unittest.TestCase):
    def test_monotonic_sequence(self):
        store = InMemoryEventStore()
        # Original envelopes with default sequence_number=0
        env1 = MessageEnvelope.create(DummyEvent(1), 1)
        env2 = MessageEnvelope.create(DummyEvent(2), 1)
        
        stored_env1 = store.append(env1)
        stored_env2 = store.append(env2)
        
        self.assertEqual(stored_env1.sequence_number, 1)
        self.assertEqual(stored_env2.sequence_number, 2)
        
        # Ensure EventStore preserved chronological order
        all_events = store.get_all()
        self.assertEqual(all_events[0].sequence_number, 1)
        self.assertEqual(all_events[1].sequence_number, 2)

    def test_o1_correlation_index_stream(self):
        store = InMemoryEventStore()
        
        env1 = MessageEnvelope.create(DummyEvent(1), 1, correlation_id="c1")
        env2 = MessageEnvelope.create(DummyEvent(2), 1, correlation_id="c2")
        env3 = MessageEnvelope.create(DummyEvent(3), 1, correlation_id="c1")
        
        store.append(env1)
        store.append(env2)
        store.append(env3)
        
        c1_stream = store.get_stream("c1")
        self.assertEqual(len(c1_stream), 2)
        self.assertEqual(c1_stream[0].payload.value, 1)
        self.assertEqual(c1_stream[1].payload.value, 3)
        # Should be chronologically ordered and with monotonic seq
        self.assertEqual(c1_stream[0].sequence_number, 1)
        self.assertEqual(c1_stream[1].sequence_number, 3)
        
        c2_stream = store.get_stream("c2")
        self.assertEqual(len(c2_stream), 1)
        self.assertEqual(c2_stream[0].payload.value, 2)
        self.assertEqual(c2_stream[0].sequence_number, 2)

if __name__ == "__main__":
    unittest.main()
