from abc import ABC, abstractmethod
from typing import Dict
from gqos.config.settings import GQOSSettings

class ISecretsProvider(ABC):
    @abstractmethod
    def get_broker_credentials(self) -> Dict[str, str]:
        pass

class LocalEnvSecretsProvider(ISecretsProvider):
    def __init__(self, settings: GQOSSettings):
        self._settings = settings
        
    def get_broker_credentials(self) -> Dict[str, str]:
        """
        Extracts credentials from Pydantic settings.
        Since they are SecretStr, we must call get_secret_value() to expose them to the adapter.
        """
        return {
            "api_key": self._settings.broker_api_key.get_secret_value(),
            "api_secret": self._settings.broker_api_secret.get_secret_value()
        }

class VaultSecretsProvider(ISecretsProvider):
    def __init__(self, vault_url: str, role_id: str):
        self.vault_url = vault_url
        self.role_id = role_id
        
    def get_broker_credentials(self) -> Dict[str, str]:
        # Future implementation
        raise NotImplementedError("Vault integration planned for future release.")
