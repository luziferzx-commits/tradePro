from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import datetime

class LogLevel:
    INFO = "INFO"
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ILogger(ABC):
    """
    ISP-compliant Logger interface.
    Minimal footprint to ensure easy implementation and testing.
    """
    @abstractmethod
    def log(self, level: str, message: str) -> None:
        pass

class IClock(ABC):
    """
    Distinguishes System Time from Market Time.
    Essential for deterministic Replay execution.
    """
    @abstractmethod
    def now(self) -> datetime:
        """Returns the current applicable time context."""
        pass

class IConfiguration(ABC):
    """
    Minimal configuration provider.
    """
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass
