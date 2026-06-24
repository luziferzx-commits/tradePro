# ADR-001: Migration to Event-Driven Architecture (Event Bus)

## Date
2026-06-23

## Status
Accepted (Planned for Phase C)

## Context (The Problem)
Currently, `main.py` is a monolithic sequential loop (`Indicators -> Setup -> ML -> Memory -> Risk -> Execute`). This creates tight coupling. If we want to add a Canary Model or swap XGBoost for a Transformer, we must rewrite the core execution loop.

## Options Considered
1. Keep sequential loop but abstract via interfaces (Strategy Pattern).
2. Refactor to Pub/Sub Event Bus (`CANDLE_CLOSED -> FEATURES_READY -> MODEL_PREDICTED`).

## Decision
We will adopt Option 2 (Pub/Sub Event Bus). 
We will introduce a `DecisionEngine` that listens to model outputs asynchronously and makes the final `BUY/SELL/SKIP` decision.

## Consequences (Impact)
- **Pros**: Highly decoupled. Easy to replay historical events (`Time Machine`). Easy to inject Canary models.
- **Cons**: Debugging requires tracing events rather than stepping through a single function. Temporary breakage during migration (Phase C).
