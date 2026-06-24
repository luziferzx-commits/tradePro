# ADR-0006: Evidence Pipeline (M4)

## Status
Accepted

## Context
GQOS requires an Evidence Platform to ensure that any domain object (e.g., Trade, Prediction) can be mathematically audited back to its source before it is considered valid or "Promoted". Due to the asynchronous nature of event-driven architectures, we cannot assume that parent artifacts will arrive at the `ArtifactRegistry` before their children.

## Alternatives Considered

1. **Reject Missing Parents Immediately**
   - *Pros*: Extremely simple to implement. Strict consistency.
   - *Cons*: Fails horribly in async environments. A delayed `Feature` event would cause the entire tree (Dataset, Prediction, Decision, Trade) to be permanently rejected unless the producers implement complex retry logic.
   
2. **Accept Invalid Graphs Temporarily**
   - *Pros*: Simple to implement.
   - *Cons*: Corrupts the `ArtifactRegistry` with dangling pointers. Violates the core principle that the Registry only contains mathematically verifiable graphs.

3. **Pending Evidence Queue (Chosen)**
   - *Pros*: Maintains strict Registry integrity while gracefully handling async network delays. When a child arrives without its parents, it is placed in the Queue. Once the parent is successfully stored, the Queue is notified and re-submits the child. A TTL prevents permanent memory leaks.
   - *Cons*: Adds state management complexity outside the Registry.

## Decision
We choose the **Pending Evidence Queue** and **Immutable Evidence Models**.

**Policies Enforced:**
1. **Dangling Parent Policy**: Any artifact with unresolved `parent_ids` is stored in the `PendingEvidenceQueue` with a TTL. It is recursively re-evaluated as new artifacts enter the Registry. If TTL expires, a `ValidationFailedEvent` is emitted and the artifact is dropped.
2. **Audit Policy**: A `LineageAuditor` validates the unbroken DFS chain of a terminal artifact and issues an `AuditReport` (which is itself an immutable `IArtifact`).
3. **Promotion Mechanism**: Artifacts are strictly immutable. Therefore, "Promotion" is modeled as a new `PromotionRecord` artifact (linking to the `AuditReport` and target artifact) and a corresponding `ArtifactPromotedEvent` is published. Existing artifacts are never updated in-place (e.g., `artifact.status = "promoted"` is forbidden).

## Consequences
- The Artifact Registry remains 100% free of broken links.
- The system handles asynchronous distributed event architectures effortlessly.
- "Promotion" is now a verifiable fact in the Registry, meaning we can audit *why* and *when* a model or trade was promoted.
