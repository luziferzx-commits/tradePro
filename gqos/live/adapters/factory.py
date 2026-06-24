from typing import Callable
from gqos.messaging.bus import IEventBus
from gqos.config.secrets import ISecretsProvider
from gqos.live.interfaces import IBrokerAdapter
from gqos.live.adapter import SandboxBrokerAdapter
from gqos.live.adapters.binance import BinanceAdapter

class AdapterFactory:
    @staticmethod
    def create_adapter(environment: str, event_bus: IEventBus, oms_callback: Callable, secrets: ISecretsProvider) -> IBrokerAdapter:
        if environment == "dev" or environment == "sandbox":
            return SandboxBrokerAdapter(event_bus, oms_callback)
        elif environment == "binance_testnet":
            return BinanceAdapter(event_bus, oms_callback, secrets, testnet=True)
        else:
            raise ValueError(f"Unknown broker environment: {environment}")
