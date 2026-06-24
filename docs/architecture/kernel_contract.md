# GQOS Kernel Contract

The Kernel is the absolute foundation (Layer 0) of the GoldBot Quant Operating System (GQOS). It acts as the Dependency Injection container and service registry.

## Kernel Guarantees

The Kernel guarantees the following for any system built upon it:

1. **Deterministic Resolve**: A request for an interface will always yield the registered implementation. If an interface is not registered, it will fail fast (throw an error immediately).
2. **Singleton Lifetime**: When registered as a Singleton, the Kernel guarantees exactly one instance exists per Kernel instance across all threads.
3. **Transient Lifetime**: When registered as Transient, the Kernel guarantees a new instance is created and returned on every resolve request.
4. **Thread Safety**: The registration and resolution processes are completely thread-safe. Multiple threads can resolve dependencies simultaneously without race conditions.
5. **No Business Dependency**: The Kernel has zero knowledge of the business domain. It does not know what a "Trade" is, what "Gold" is, or what "MT5" is. It only manages pure computational infrastructure.

## Rules of Engagement

- **Composition Root Only**: Do not call `Kernel.resolve()` from inside your classes. Inject dependencies via constructors. `Kernel.resolve()` is reserved for the `main.py` entry point.
- **Interface Segregation**: All registered services must be backed by an abstract interface (e.g., `ILogger`).
- **Simplicity Before Sophistication**: The Kernel must remain the simplest component in the entire OS.
