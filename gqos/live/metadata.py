import requests
from decimal import Decimal
from typing import Dict, Optional

class MetadataCache:
    def __init__(self, base_url: str = "https://testnet.binance.vision"):
        self.base_url = base_url
        self.rules: Dict[str, Dict[str, Decimal]] = {}
        
    def refresh(self):
        """Fetches exchangeInfo from Binance and parses rules."""
        response = requests.get(f"{self.base_url}/api/v3/exchangeInfo", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        for symbol_info in data.get("symbols", []):
            symbol = symbol_info["symbol"]
            rules = {}
            for f in symbol_info.get("filters", []):
                if f["filterType"] == "PRICE_FILTER":
                    rules["tick_size"] = Decimal(f["tickSize"])
                elif f["filterType"] == "LOT_SIZE":
                    rules["step_size"] = Decimal(f["stepSize"])
                elif f["filterType"] == "NOTIONAL":
                    rules["min_notional"] = Decimal(f["minNotional"])
            
            self.rules[symbol] = rules
            
    def get_rules(self, symbol: str) -> Optional[Dict[str, Decimal]]:
        return self.rules.get(symbol)
