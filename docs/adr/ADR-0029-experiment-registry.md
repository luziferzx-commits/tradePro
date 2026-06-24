# ADR-0029: Experiment Registry & Artifact Signatures

## Context

In M13C, GQOS required a persistence layer for saving Research results. Quantitative research artifacts must be permanently auditable. If a researcher runs an experiment, the results (and the Markdown Strategy Card used to present to the Investment Committee) must be cryptographically locked to prevent post-generation tampering.

## Decision 1: Disk Persistence over Database

We chose to serialize `ExperimentResult`s directly to the filesystem (e.g., `.gqos/experiments/<experiment_id>/`) rather than using a relational database or remote cloud storage initially.

* **Rationale**: Filesystem persistence is highly portable, plays well with Git LFS if needed, and allows easy manual inspection of JSON and Markdown. It adheres to the M13 Scope Lock which prohibited external DB backends.

## Decision 2: The Artifact Signature (`artifact.sha256`)

The `ExperimentRegistry` computes a master SHA-256 hash by combining the content hashes of *all* files within the experiment bundle (`definition.json`, `result.json`, `manifest.json`, and `strategy_card.md`).

* **Rationale**: It is not enough to hash the Python dataclasses in memory. By hashing the final written file contents (including the Markdown report), the system can detect if a user manually opens `strategy_card.md` in a text editor and alters a Sharpe ratio from `1.5` to `2.5`. The `verify_experiment` method will fail immediately upon reload.

## Decision 3: Strategy Card Generator as a Pure Formatter

The `StrategyCardGenerator` accepts pre-calculated metrics inside the `StrategyCard` object and formats them into Markdown. It does *not* average or aggregate Fold metrics dynamically.

* **Rationale**: Different strategies require different aggregation penalties for out-of-sample variance. The generator should be entirely devoid of financial logic; it is strictly a presentation formatter.

## Status

Approved and implemented in M13C.
