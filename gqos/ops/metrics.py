from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server
from typing import Dict

class MetricsExporter:
    def __init__(self, engine_version: str = "1.0.0", schema_version: str = "1.0"):
        self.engine_version = engine_version
        self.schema_version = schema_version
        
        # Metadata
        self.info = Info('gqos_build_info', 'Build and version info')
        self.info.info({'engine_version': engine_version, 'schema_version': schema_version})
        
        # Counters
        self.total_orders = Counter('gqos_orders_total', 'Total orders generated', ['strategy'])
        self.total_fills = Counter('gqos_fills_total', 'Total fills received', ['symbol'])
        self.total_rejects = Counter('gqos_rejects_total', 'Total orders rejected', ['reason'])
        self.drift_warnings = Counter('gqos_drift_warnings_total', 'Total feature drift warnings', ['feature_id'])
        self.kill_switch_triggers = Counter('gqos_kill_switch_triggers_total', 'Total kill switch triggers')
        
        # Gauges
        self.live_equity = Gauge('gqos_live_equity', 'Current total portfolio equity', ['portfolio_id'])
        self.margin_used = Gauge('gqos_margin_used', 'Current margin / capital utilized', ['portfolio_id'])
        self.position_size = Gauge('gqos_position_size', 'Current net position quantity', ['symbol'])
        
        # Histograms
        self.forecast_latency = Histogram('gqos_forecast_latency_seconds', 'Latency of alpha generation')
        self.optimizer_latency = Histogram('gqos_optimizer_latency_seconds', 'Latency of portfolio optimization')
        self.oms_latency = Histogram('gqos_oms_latency_seconds', 'Latency of OMS routing')
        self.broker_latency = Histogram('gqos_broker_latency_seconds', 'Latency to get ACK from broker')
        self.fill_latency = Histogram('gqos_fill_latency_seconds', 'Latency from ACK to first Fill')

    def start_server(self, port: int = 8000):
        start_http_server(port)
        print(f"Prometheus metrics exporter started on port {port}")
