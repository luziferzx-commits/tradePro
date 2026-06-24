import unittest
from gqos.messaging.store import InMemoryEventStore
from gqos.messaging.contracts import MessageEnvelope, Event
from dataclasses import dataclass

@dataclass(frozen=True)
class DummyEvent(Event):
    value: int

class TestEventStore(unittest.TestCase):
    def test_append_and_get_all(self):
        store = InMemoryEventStore()
        env1 = MessageEnvelope.create(DummyEvent(1), 1)
        env2 = MessageEnvelope.create(DummyEvent(2), 1)
        
        store.append(env1)
        store.append(env2)
        
        all_events = store.get_all()
        self.assertEqual(len(all_events), 2)
        self.assertEqual(all_events[0].payload.value, 1)
        self.assertEqual(all_events[1].payload.value, 2)
        
    def test_get_stream(self):
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

if __name__ == "__main__":
    unittest.main()
