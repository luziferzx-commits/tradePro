import os
import pytest
from pydantic import ValidationError
from gqos.config.settings import GQOSSettings, load_settings
from gqos.config.secrets import LocalEnvSecretsProvider

def test_config_schema_validation():
    # Valid config
    os.environ["GQOS_BROKER_API_KEY"] = "test-key"
    os.environ["GQOS_BROKER_API_SECRET"] = "test-secret"
    os.environ["GQOS_ENVIRONMENT"] = "dev"
    os.environ["GQOS_MAX_ORDER_QUANTITY"] = "500.0"
    
    settings = GQOSSettings()
    assert settings.environment == "dev"
    assert settings.max_order_quantity == 500.0
    
def test_invalid_config_rejects_startup():
    # Invalid environment
    os.environ["GQOS_ENVIRONMENT"] = "invalid_env"
    
    with pytest.raises(ValidationError):
        GQOSSettings()
        
    # Reset for next tests
    os.environ["GQOS_ENVIRONMENT"] = "dev"
    
def test_secrets_provider_and_redaction():
    os.environ["GQOS_BROKER_API_KEY"] = "secret_key_123"
    os.environ["GQOS_BROKER_API_SECRET"] = "secret_token_abc"
    
    settings = GQOSSettings()
    provider = LocalEnvSecretsProvider(settings)
    
    creds = provider.get_broker_credentials()
    assert creds["api_key"] == "secret_key_123"
    assert creds["api_secret"] == "secret_token_abc"
    
    # Verify the SecretStr redacts when printed/logged directly
    assert "secret_key_123" not in str(settings.broker_api_key)
    assert "**********" in str(settings.broker_api_key)

if __name__ == "__main__":
    test_config_schema_validation()
    test_invalid_config_rejects_startup()
    test_secrets_provider_and_redaction()
    print("M21 Config Tests Passed!")
