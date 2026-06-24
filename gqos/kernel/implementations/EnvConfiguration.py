import os
from typing import Any
from gqos.kernel.interfaces import IConfiguration

class EnvConfiguration(IConfiguration):
    """
    Implementation of IConfiguration that reads from environment variables.
    """
    def get(self, key: str, default: Any = None) -> Any:
        return os.environ.get(key, default)
