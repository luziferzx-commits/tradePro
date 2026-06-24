# ADR-0001: Kernel Foundation & Dependency Injection

## Status
Accepted

## Context
As GQOS evolves from a standalone trading script into a full-fledged Quantitative Operating System, the monolithic architecture (`main.py` referencing global variables and hardcoded implementations) has become a severe liability. 
We need a unified way to inject core services (Logger, Clock, Config) into business logic without coupling the logic to the infrastructure.

## Alternatives Considered

1. **Global Singletons**
   - *Pros*: Very easy to implement. Readily available anywhere.
   - *Cons*: Hidden dependencies. Makes unit testing very difficult (mocking is messy). Breaches isolation between layers.
2. **Service Locator Pattern**
   - *Pros*: Centralized access point for all services.
   - *Cons*: Classes still depend on the Service Locator itself, masking their true dependencies.
3. **Dependency Injection (DI) Container (Kernel)**
   - *Pros*: Classes declare their dependencies explicitly via Constructor Injection. The composition happens entirely at the root. Decouples layers completely.
   - *Cons*: Slightly higher upfront complexity. Requires a dedicated Composition Root.

## Decision
We choose **Dependency Injection Container (Kernel)**. 
We will build a minimal thread-safe DI container (`Kernel`) that resolves interfaces to implementations.

## Rules Enforced
1. **The Kernel must be boring**: It contains no business logic (no Trade, MT5, or Model concepts).
2. **Composition Root Only**: `Kernel.resolve()` must only be called at the highest level of the application (e.g., `main.py`). Downstream classes must receive dependencies via their constructors.

## Consequences
- Testing becomes trivial as interfaces can be easily mocked and passed via constructors.
- The `gqos/kernel/` package acts as the absolute bottom layer (Layer 0) of the OS.
- Moving forward, all new services must define an Interface (e.g., `IEventBus`) and be registered in the Kernel.
