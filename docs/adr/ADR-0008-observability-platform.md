# ADR-0008: Observability Platform Separation (M6)

## Status
Accepted

## Context
As GQOS matures into a full-fledged Quantitative Operating System, we must gain complete visibility into its runtime behavior (Metrics, Tracing, Health) without influencing the core business logic or corrupting the evidence ledgers.

## Decision 1: Observability as an Envelope Wrapper

We implemented the `ObservabilityEngine` utilizing the Decorator pattern over `IEventBus` and `ICommandBus`. 
**Rationale:** 
- The core Execution Engine remains completely unaware of telemetry collection.
- Metrics (Counters, Histograms) are automatically incremented based on the `MessageEnvelope` passing through the bus.
- This adheres strictly to the requirement: "Observe the platform without influencing the platform".

## Decision 2: Separation of TraceStore and EventStore

Traces (chronological profiling of spans) are recorded in a dedicated `TraceStore`, rather than being emitted as Domain Events into the `EventStore`.
**Rationale:**
- **Ledger Bloat**: If every operation emitted a `TraceEvent`, the `EventStore` would quickly become bloated with non-business data.
- **Causality Integrity**: The `EventStore` is the strict chronological ledger of what *happened* in the business domain. Traces are meta-information about *how long* those things took to happen. Mixing them complicates deterministic replays and audits.

## Decision 3: EventStore Indexing and Sequence Numbers

To support high-performance replays and deterministic audits, we paid down M5 technical debt by:
1. Adding a strictly monotonic `sequence_number` to every `MessageEnvelope` as it enters the `EventStore`.
2. Implementing an O(1) correlation index (`Dict[str, List[int]]`) in the `InMemoryEventStore`.
**Rationale:**
- Replaying a specific execution run (via `correlation_id`) now avoids an O(n) scan of the entire history ledger.
- The `sequence_number` guarantees perfect event ordering reconstruction even if the original timestamps have microscopic overlaps.

## Roadmap and Technical Debt

To prepare for distributed execution and extreme throughput (100M+ events), the following architectural evolutions are planned but intentionally deferred:
1. **Sequence Number**: Transition from a local counter (`self._sequence += 1`) to a partition sequence, and eventually to a Global Logical Clock (e.g., Vector Clocks) for distributed determinism.
2. **Metrics Histogram Memory**: To prevent RAM exhaustion, transition `Histograms` from raw `List[float]` to bounded `HDR Histogram` or `DDSketch`.
3. **TraceStore Lookup**: Refactored in M6.5 to use an O(1) Dictionary `Dict[str, List[TraceSpan]]` keyed by `trace_id`.
4. **Health Monitor Weights**: Introduce criticality weights (`Critical` vs `NonCritical`) for subsystems so that non-critical failures (like a metrics exporter going down) yield a `DEGRADED` system rather than a complete `FAILED` halt.
