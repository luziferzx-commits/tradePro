from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from typing import Optional

class GQOSSettings(BaseSettings):
    # Core
    environment: str = Field(default="dev", pattern="^(dev|staging|prod)$")
    engine_name: str = "gqos-live-engine"
    
    # Execution
    max_order_quantity: float = Field(default=100.0, gt=0)
    kill_switch_timeout_seconds: float = Field(default=0.5, gt=0)
    
    # Portfolio
    initial_capital: float = Field(default=100000.0, gt=0)
    base_currency: str = "USD"
    
    # Secrets (Loaded from .env or SecretsProvider)
    broker_api_key: SecretStr = Field(...)
    broker_api_secret: SecretStr = Field(...)
    
    model_config = SettingsConfigDict(env_prefix='GQOS_', env_file='.env', extra='ignore')
    
def load_settings() -> GQOSSettings:
    """
    Loads settings and fails fast if required fields are missing.
    """
    return GQOSSettings()
