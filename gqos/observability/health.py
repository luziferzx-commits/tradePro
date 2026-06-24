from enum import Enum
from typing import Dict, Protocol

class HealthStatus(Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"

class IHealthCheck(Protocol):
    def check_health(self) -> HealthStatus:
        pass

class HealthMonitor:
    def __init__(self):
        self._checks: Dict[str, IHealthCheck] = {}

    def register(self, name: str, check: IHealthCheck):
        self._checks[name] = check

    def get_system_health(self) -> HealthStatus:
        statuses = []
        for name, check in self._checks.items():
            try:
                status = check.check_health()
            except Exception:
                status = HealthStatus.FAILED
            statuses.append(status)
            
        if HealthStatus.FAILED in statuses:
            return HealthStatus.FAILED
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.OK
