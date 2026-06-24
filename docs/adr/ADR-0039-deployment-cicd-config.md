# ADR-0039: Deployment, CI/CD, and Configuration Boundary

## Context

To reach true production readiness (M21), GQOS must move away from manual script execution, hardcoded variables, and loosely managed secrets. Deploying to a live exchange with real capital demands rigorous verification pipelines, container isolation, and absolute configuration determinism.

## Decision 1: Immutable Configuration via Pydantic

We adopted `pydantic-settings` to manage all application configurations (`gqos/config/settings.py`).

* **Rationale**: In quantitative trading, a typo in `max_order_quantity` (e.g., passing a string instead of a float, or an extra zero) can lead to catastrophic financial loss. Pydantic enforces strict type-checking at boot. If a required environment variable is missing, or a type casting fails, the system immediately crashes during startup (Fail Fast), completely preventing it from initializing the trading engine in an undefined state.

## Decision 2: Abstract Secrets Provider

We introduced the `ISecretsProvider` interface.

* **Rationale**: Hardcoding API keys or committing them to Git is a critical security vulnerability. By abstracting the retrieval of credentials behind a `SecretsProvider`, we can securely inject them via `.env` locally (using Pydantic's `SecretStr` to auto-redact from logs) while maintaining the structural boundary to swap to HashiCorp Vault or AWS Secrets Manager in institutional production deployments without altering the core OMS logic.

## Decision 3: Deterministic Containerization

We implemented a multi-stage `Dockerfile`.

* **Rationale**: Dependency drift is a major cause of "works on my machine" failures. The multi-stage build securely isolates the build dependencies, runs as a non-root `gqos_user` for container security, and ensures the execution environment is perfectly reproducible across staging and production clusters.

## Decision 4: Safe Rollout Architecture

We implemented a `rollout.py` script that interrogates the `/health`, `/live`, and `/ready` endpoints of the new container before concluding a successful deployment.

* **Rationale**: Deployments in trading are high-risk. A "Blue-Green" or "Canary" deployment script must verify that the new version of the engine has successfully booted, parsed its configuration, connected to the message bus, and is returning HTTP 200 on its readiness probe. If these fail, the script immediately triggers a rollback, ensuring no live traffic (or market data) is routed to a broken container.

## Status

Approved and implemented in M21.
