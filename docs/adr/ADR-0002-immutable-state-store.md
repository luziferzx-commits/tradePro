# ADR-0002: Immutable State Store

## Status
Accepted

## Context
As the GoldBot Quant Operating System (GQOS) transitions to a robust architecture, the reliance on mutable global variables (e.g., modifying dicts across different modules) poses a severe risk to traceabilty, thread-safety, and deterministic replayability. We need a way to manage the application's global state safely.

## Alternatives Considered

1. **Mutable Global Dictionary**
   - *Pros*: Simple, fast.
   - *Cons*: Highly prone to race conditions. Impossible to track changes or revert. Breaks Replay Engine determinism.
2. **Actor Model (Message Passing State)**
   - *Pros*: Excellent concurrency model.
   - *Cons*: Overkill for the current phase; adds significant latency and complexity.
3. **Immutable State Store with Snapshots**
   - *Pros*: Every state change yields a new frozen Snapshot. Guarantees 100% traceabilty. Snapshots can be diffed, versioned, and saved for perfect Replay capability.
   - *Cons*: Memory overhead from creating new objects on every mutation.

## Decision
We choose the **Immutable State Store with Snapshots**. 
State will be represented as a frozen generic tree structure (`StateSnapshot`). 
All mutations must be routed through a central `StateManager`, which applies the change and generates a monotonically versioned new Snapshot.

## Rules Enforced
1. **Immutable Snapshots**: Once created, a `StateSnapshot` cannot be mutated.
2. **Monotonic Versioning**: Every mutation increments the version counter linearly (e.g., 0, 1, 2).
3. **Single Writer, Multiple Readers**: The `StateManager` uses a Read-Write lock paradigm (or thread-safe exclusive writer lock) to prevent race conditions during mutations.
4. **Zero Business Logic**: The state store only manages keys, values, and versions. It does not enforce domain models (no `Position` or `Trade` classes yet).

## Consequences
- The system achieves absolute determinism. We can time-travel to any exact state version during debugging.
- The overhead of object creation must be aggressively benchmarked and kept under latency budgets (Creation < 20us).
