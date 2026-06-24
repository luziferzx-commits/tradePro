from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import threading
import array

class IMetricsSink(ABC):
    @abstractmethod
    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        pass

    @abstractmethod
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        pass
        
    @abstractmethod
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        pass

class InMemoryMetricsSink(IMetricsSink):
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, array.array] = {}
        self._lock = threading.RLock()
        
    def _key(self, name: str, labels: Dict[str, str] = None) -> str:
        if not labels:
            return name
        if len(labels) == 1:
            k, v = next(iter(labels.items()))
            return f"{name}{{{k}={v}}}"
        label_str = ",".join([f"{k}={v}" for k, v in sorted(labels.items())])
        return f"{name}{{{label_str}}}"

    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        key = self._key(name, labels)
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + value

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        key = self._key(name, labels)
        with self._lock:
            self.gauges[key] = value

    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        key = self._key(name, labels)
        with self._lock:
            if key not in self.histograms:
                self.histograms[key] = array.array('d')
            self.histograms[key].append(value)

class MetricsRegistry:
    def __init__(self, sink: IMetricsSink):
        self._sink = sink

    def increment(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        self._sink.increment_counter(name, value, labels)
        
    def gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        self._sink.set_gauge(name, value, labels)
        
    def histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        self._sink.record_histogram(name, value, labels)
