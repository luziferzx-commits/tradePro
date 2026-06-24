import threading
from typing import List, Dict, Optional, NamedTuple

class TraceSpan(NamedTuple):
    trace_id: str
    span_id: int
    name: str
    start_time: float
    end_time: float
    parent_span_id: Optional[str] = None
    labels: tuple = tuple()
    
    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000.0

class TraceStore:
    def __init__(self):
        self._spans: Dict[str, List[TraceSpan]] = {}
        self._lock = threading.RLock()
        self._max_spans = 100
        
    def record(self, span: TraceSpan):
        with self._lock:
            if span.trace_id not in self._spans:
                self._spans[span.trace_id] = []
            span_list = self._spans[span.trace_id]
            span_list.append(span)
            if len(span_list) > self._max_spans:
                span_list.pop(0)
            
    def get_trace(self, trace_id: str) -> List[TraceSpan]:
        with self._lock:
            return self._spans.get(trace_id, []).copy()

class TraceManager:
    def __init__(self, store: TraceStore):
        self._store = store

    def record_span(self, trace_id: str, span_id: str, name: str, start_time: float, end_time: float, labels: Dict[str, str] = None):
        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            start_time=start_time,
            end_time=end_time,
            labels=labels or {}
        )
        self._store.record(span)
