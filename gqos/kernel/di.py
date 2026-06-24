import threading
from typing import Type, TypeVar, Callable, Dict, Any, Optional

T = TypeVar('T')

class Lifetime:
    SINGLETON = "SINGLETON"
    TRANSIENT = "TRANSIENT"

class Kernel:
    """
    The Core Dependency Injection Container for GQOS.
    Thread-safe, deterministic, business-agnostic.
    Must ONLY be invoked from the Composition Root.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._registry: Dict[Type, Dict[str, Any]] = {}
        self._singletons: Dict[Type, Any] = {}
        self._registry_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'Kernel':
        """Singleton pattern for the Kernel itself."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Primarily for testing."""
        with cls._lock:
            cls._instance = None

    def register(self, interface: Type[T], implementation_factory: Callable[[], T], lifetime: str = Lifetime.SINGLETON) -> None:
        """Register a dependency factory with a specific lifetime."""
        with self._registry_lock:
            self._registry[interface] = {
                "factory": implementation_factory,
                "lifetime": lifetime
            }
            # Clear singleton instance if re-registered
            if interface in self._singletons:
                del self._singletons[interface]

    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve a dependency.
        This should ONLY be called at the Composition Root to assemble the application graph.
        """
        with self._registry_lock:
            if interface not in self._registry:
                raise ValueError(f"Interface {interface.__name__} is not registered in the Kernel.")
            
            registration = self._registry[interface]
            
            if registration["lifetime"] == Lifetime.SINGLETON:
                if interface not in self._singletons:
                    self._singletons[interface] = registration["factory"]()
                return self._singletons[interface]
            
            # Transient: always create a new instance
            return registration["factory"]()
