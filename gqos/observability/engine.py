from typing import Type, Callable, Any
from gqos.messaging.interfaces import IEventBus, ICommandBus
from gqos.messaging.contracts import Event, Command, MessageEnvelope
from gqos.observability.metrics import MetricsRegistry
from gqos.observability.tracing import TraceManager
import time
import uuid

class ObservableEventBus(IEventBus):
    def __init__(self, inner: IEventBus, metrics: MetricsRegistry, tracer: TraceManager):
        self._inner = inner
        self._metrics = metrics
        self._tracer = tracer

    def subscribe(self, event_type: Type[Event], handler: Callable[[MessageEnvelope[Event]], None]) -> None:
        self._inner.subscribe(event_type, handler)

    def unsubscribe(self, event_type: Type[Event], handler: Callable[[MessageEnvelope[Event]], None]) -> None:
        self._inner.unsubscribe(event_type, handler)

    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        start_time = time.time()
        
        # Call inner bus
        self._inner.publish(envelope)
        
        end_time = time.time()
        event_name = type(envelope.payload).__name__
        
        self._metrics.increment("events_published_total", 1, {"event": event_name})
        self._metrics.histogram("event_publish_latency_ms", (end_time - start_time) * 1000, {"event": event_name})
        
        if envelope.trace_id:
            self._tracer.record_span(
                trace_id=envelope.trace_id,
                span_id=time.time_ns(),
                name=f"Publish:{event_name}",
                start_time=start_time,
                end_time=end_time,
                labels=(("correlation_id", str(envelope.correlation_id)),)
            )

class ObservableCommandBus(ICommandBus):
    def __init__(self, inner: ICommandBus, metrics: MetricsRegistry, tracer: TraceManager):
        self._inner = inner
        self._metrics = metrics
        self._tracer = tracer

    def register_handler(self, command_type: Type[Command], handler: Callable[[MessageEnvelope[Command]], Any]) -> None:
        self._inner.register_handler(command_type, handler)

    def dispatch(self, envelope: MessageEnvelope[Command]) -> Any:
        start_time = time.time()
        
        try:
            result = self._inner.dispatch(envelope)
            status = "success"
            return result
        except Exception as e:
            status = "error"
            self._metrics.increment("commands_failed_total", 1, {"command": type(envelope.payload).__name__})
            raise e
        finally:
            end_time = time.time()
            cmd_name = type(envelope.payload).__name__
            
            self._metrics.increment("commands_dispatched_total", 1, {"command": cmd_name, "status": status})
            self._metrics.histogram("command_dispatch_latency_ms", (end_time - start_time) * 1000, {"command": cmd_name})
            
            if envelope.trace_id:
                self._tracer.record_span(
                    trace_id=envelope.trace_id,
                    span_id=time.time_ns(),
                    name=f"Dispatch:{cmd_name}",
                    start_time=start_time,
                    end_time=end_time,
                    labels=(("status", status), ("correlation_id", str(envelope.correlation_id)))
                )
