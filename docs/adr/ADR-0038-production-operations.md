# ADR-0038: Production Operations & Observability

## Context

As GQOS transitions from a research platform to a live production trading system (M20), operating blindly is no longer acceptable. If an order is rejected, if alpha features drift, or if the Kill Switch triggers, the Operations team needs immediate visibility. Furthermore, institutional trading requires absolute auditability to prove deterministic execution.

## Decision 1: Prometheus & Grafana Over Native Dashboards

We chose to integrate `prometheus_client` to expose metrics via a `/metrics` HTTP endpoint, rather than building custom React/CLI dashboards directly into the trading engine.

* **Rationale**: Prometheus is the industry standard for time-series observability. By exporting metrics (Gauges for Equity/Positions, Counters for Fills/Rejects/Drift, Histograms for Latency), we decouple the trading logic from the visualization layer. We include a standard `docker-compose.yml` to spin up Grafana independently, ensuring the trading engine remains lightweight and focused on low-latency execution.

## Decision 2: Hash-Chained Immutable Audit Log

We implemented an `AuditLogWriter` that intercepts all non-tick events from the `LocalEventBus` and appends them to a JSONL file. Each entry contains a `hash` computed from the previous event's hash + the current payload.

* **Rationale**: To achieve true Event Sourcing and institutional-grade compliance, log files cannot be vulnerable to tampering or silent corruption. The hash chain guarantees that the sequence of events is immutable. We explicitly filter out high-frequency noise like `MarketDataEvent` (ticks) to prevent the audit log from growing to terabytes per week, routing ticks to a separate Market Archive instead.

## Decision 3: Event Replay Verification

We built a `ReplayEngine` capable of reading the `audit_log.jsonl`, verifying the hash chain integrity, and reconstructing the `AccountingEngine` state identically.

* **Rationale**: Snapshots are useful for quick recovery, but they are opaque. Event Replay proves that the system is perfectly deterministic. If a bug is discovered in production, the operations team can extract the audit log, replay the exact sequence of lifecycle events locally, and reproduce the state. The replay is only considered valid if the `Replay Hash` matches the `Production Hash`.

## Decision 4: JSON Structured Logging

Standard `print()` or plain-text `logging` was replaced with a custom `JsonFormatter`.

* **Rationale**: In modern DevOps (e.g., ELK stack, Datadog, Loki), unstructured text logs are impossible to query efficiently. By forcing all logs to emit JSON with explicit fields (`timestamp`, `level`, `component`, `run_id`, `correlation_id`), the operations team can effortlessly filter logs to trace the lifecycle of a specific order across multiple internal modules.

## Status

Approved and implemented in M20.
