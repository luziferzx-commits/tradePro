import unittest
from gqos.messaging.contracts import Event, Command, MessageEnvelope
from gqos.messaging.bus import LocalEventBus, LocalCommandBus
from gqos.observability.metrics import MetricsRegistry, InMemoryMetricsSink
from gqos.observability.tracing import TraceManager, TraceStore
from gqos.observability.engine import ObservableEventBus, ObservableCommandBus
from dataclasses import dataclass

@dataclass(frozen=True)
class DummyEvent(Event):
    pass

@dataclass(frozen=True)
class DummyCommand(Command):
    pass

class DummyLogger:
    def log(self, level, msg):
        pass

class TestObservability(unittest.TestCase):
    def test_observable_buses(self):
        logger = DummyLogger()
        inner_event_bus = LocalEventBus(logger)
        inner_command_bus = LocalCommandBus(logger)
        
        sink = InMemoryMetricsSink()
        metrics = MetricsRegistry(sink)
        
        trace_store = TraceStore()
        tracer = TraceManager(trace_store)
        
        obs_event_bus = ObservableEventBus(inner_event_bus, metrics, tracer)
        obs_command_bus = ObservableCommandBus(inner_command_bus, metrics, tracer)
        
        # Test Event
        obs_event_bus.publish(MessageEnvelope.create(DummyEvent(), 1, trace_id="trace-123"))
        
        # Check metrics
        key = "events_published_total{event=DummyEvent}"
        self.assertEqual(sink.counters[key], 1)
        
        # Check traces
        traces = trace_store.get_trace("trace-123")
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].name, "Publish:DummyEvent")
        
        # Test Command
        obs_command_bus.register_handler(DummyCommand, lambda env: "ok")
        obs_command_bus.dispatch(MessageEnvelope.create(DummyCommand(), 1, trace_id="trace-124"))
        
        key_cmd = "commands_dispatched_total{command=DummyCommand,status=success}"
        self.assertEqual(sink.counters[key_cmd], 1)

if __name__ == "__main__":
    unittest.main()
