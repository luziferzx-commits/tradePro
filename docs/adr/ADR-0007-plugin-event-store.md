# ADR-0007: Plugin Architecture and Dual-Store Design (M5)

## Status
Accepted

## Context
As GQOS transitions into the Execution Platform (Phase 2), we need to integrate real-world actions (e.g., executing trades via a broker) while preserving the system's deterministic and auditable nature. We need a way to persistently log commands and events, and a way to route commands to isolated execution handlers (Plugins).

## Decision 1: Dual-Store Architecture

We have established two distinct storage mechanisms:
1. **EventStore**: An append-only, strictly chronological ledger that records `MessageEnvelope`s (both Commands and Events). It answers the question: *"What happened, and in what order?"* It explicitly **forbids** deduplication.
2. **ArtifactRegistry**: A content-addressed, cryptographic graph of domain objects (e.g., `Trade`, `Prediction`). It answers the question: *"What verifiable facts exist, and what is their lineage?"* It explicitly **enforces** deduplication and integrity.

**Why not a single store?**
Merging these concerns causes severe complexity. If an identical `Trade` is executed twice by mistake, the `EventStore` must record two `TradeExecutedEvent`s to reflect reality. However, the `ArtifactRegistry` treats them as the identical cryptographic fact. Keeping them separate guarantees that we have both a perfect chronological replay ledger AND a mathematically pure evidence graph.

## Decision 2: Exactly-One Command Routing

The `ExecutionEngine` orchestrates the `LocalCommandBus` and `LocalEventBus`. 
For Plugins handling `Command`s, we enforce an **Exactly-One Handler** policy.

**Alternatives Considered:**
- *Priority-based routing*: Allows multiple plugins to subscribe to `ExecuteTradeCommand` and executes the one with the highest priority. Rejected because it introduces ambiguity and makes deterministic replays significantly harder to reason about.
- *Round-robin / Load-balancing*: Rejected. GQOS is an evidence-first platform, not a microservices mesh. Determinism is paramount.

**Resolution:**
If two plugins register to handle the same Command, the `ExecutionEngine` will intentionally fail at startup with a `ConfigurationError`.

## Decision 3: Plugin Isolation from Registry

Plugins are strictly prohibited from directly accessing or mutating the `ArtifactRegistry`. 
A Plugin's sole responsibility is: `Command -> [Execution Logic] -> Event`.
The `ExecutionEngine` binds the `EvidenceCollector` to the `EventBus`. When the Plugin emits a `TradeExecutedEvent`, the `EvidenceCollector` intercepts it, validates the graph (Dangling Parents check), and stores it in the `ArtifactRegistry`.

**Consequences:**
- The Artifact Registry's integrity cannot be compromised by a rogue or poorly written Plugin.
- All evidence must pass through the rigorous Evidence Platform pipeline.
- Developers writing new integrations (e.g., Binance Plugin) do not need to understand the cryptographic graph; they only need to emit standard Events.
