# ADR-0004: Immutable Domain Models & Deterministic Artifacts

## Status
Accepted

## Context
As GQOS moves to support a fully traceable Artifact Graph, passing raw dictionaries or mutable objects between components destroys lineage and type safety. We must enforce strict Domain-Driven Design (DDD) principles where Domain Models encapsulate business rules entirely separate from Infrastructure (Persistence and Transport).

## Alternatives Considered

1. **Raw Dictionaries / JSON**
   - *Pros*: Extremely flexible, easy to serialize.
   - *Cons*: No type safety. No constructor validation. Prone to silent data errors. Breaks the Artifact Graph lineage.
2. **Mutable Objects (Standard Python Classes)**
   - *Pros*: Supports behavior and validation.
   - *Cons*: Difficult to guarantee reproducible hashes for `artifact_id`. Risky in a highly concurrent environment.
3. **ORM Models (e.g., SQLAlchemy)**
   - *Pros*: Combines domain and persistence.
   - *Cons*: Couples business rules to the database schema. Violates Clean Architecture.
4. **Immutable Dataclasses (Frozen) with Value Objects**
   - *Pros*: Strict type safety. Automatic constructor validation. 100% thread-safe. Predictable and deterministic hashing for `artifact_id`.

## Decision
We choose **Immutable Dataclasses** for the Domain Layer.
- **Value Objects**: Basic types like `Price`, `Probability`, `LotSize` are encapsulated as immutable Value Objects that validate themselves on creation.
- **ArtifactID Policy**: 
  - **SHA256(Content)**: Used for all pure Domain Objects (Dataset, Feature, Prediction, Decision, Trade, Evidence). Ensures two objects with the identical data yield the exact same Artifact ID, enabling deduplication and deterministic replay.
  - **UUIDv7**: Used only for temporal/contextual identifiers (RunID, SessionID) where chronological sorting is required.
- **Composition over Inheritance**: Deep inheritance chains (e.g., Trade inheriting from Decision) are banned. We use composition (Trade *has* a Decision).
- **Domain Isolation**: Domain objects have zero knowledge of `Messaging` (no `.publish()`) or `Persistence` (no `.save()`).

## Consequences
- Impossible to represent an invalid state (e.g., Probability = 2.5) because the Value Object constructor rejects it immediately.
- Hashing overhead must be benchmarked to ensure creating 100,000 artifacts remains within latency budgets.
- Replay engine can perfectly match historical artifacts by comparing their SHA256 hashes.
