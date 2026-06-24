# ADR-0005: Artifact Registry (Phase 1)

## Status
Accepted

## Context
GQOS artifacts (Domain Objects) need a central repository to store and retrieve them. This registry forms the basis of the Evidence Platform. If we couple this directly to a SQL or NoSQL database now, we introduce infrastructure complexity before proving the core concepts (Content Addressing, Integrity, and Lineage).

## Alternatives Considered

1. **Direct Relational Database (SQLAlchemy / PostgreSQL)**
   - *Pros*: Mature, supports complex queries.
   - *Cons*: High impedance mismatch with deep object graphs (Lineage). Requires migrations, schemas, and operational overhead.
2. **Document Store (MongoDB)**
   - *Pros*: Good for JSON-like documents.
   - *Cons*: Still introduces external infrastructure.
3. **In-Memory Artifact Registry (Dictionary-backed)**
   - *Pros*: Zero setup. Enforces interfaces (`store`, `get`, `get_lineage`). Perfect for proving Determinism, Lineage Traversal, and Integrity validation.
   - *Cons*: Ephemeral. Not for production use.

## Decision
We choose **In-Memory Artifact Registry** for Phase 1. 

**Policies Enforced:**
1. **Immutability & Integrity**: `get()` will dynamically re-hash the retrieved object. If the hash doesn't match the `artifact_id` it was stored under, an `IntegrityError` is thrown. Objects are returned directly, relying strictly on Python's frozen dataclasses to prevent accidental mutation.
2. **Duplicate Store (Idempotency)**: If `store()` is called with an `artifact_id` that already exists, it silently succeeds and returns the existing artifact. Artifacts are content-addressable; if the hash matches, the content is identical.
3. **Lineage Traversal**: `get_lineage()` performs a **Breadth-First Search (BFS)** traversal of the `parent_ids` graph. Cycles in the graph are explicitly detected and raise a `CycleDetectedError`.
4. **Schema Evolution**: Every artifact must declare a `schema_version`.

## Consequences
- Fast, zero-overhead testing for M3.
- Switching to a persistent store in Phase 2 merely requires implementing `IArtifactRegistry` with a database client, without changing the architecture.
