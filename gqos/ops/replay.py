import json
import hashlib
from decimal import Decimal
from typing import Dict, Any

from gqos.common.enums import TradeDirection
from gqos.messaging.bus import LocalEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.accounting.engine import AccountingEngine
from gqos.portfolio.manager import PortfolioManager

class MockFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        return Decimal('0'), "USD"

class MockFxConverter:
    def convert(self, amount, from_curr, to_curr):
        return amount

class ReplayEngine:
    def __init__(self, audit_filepath: str):
        self.filepath = audit_filepath
        
        self.bus = LocalEventBus(None)
        self.accounting = AccountingEngine(self.bus, MockFeeModel(), MockFxConverter())
        self.portfolio = PortfolioManager("ReplayPort", Decimal('100000.0'))
        
    def replay(self) -> str:
        last_hash = "0" * 64
        
        # Mappings of event names to their dataclasses can be tricky if we don't have a global registry.
        # But AccountingEngine only cares about TradeExecutedEvent, PositionOpenedEvent, etc.
        # Wait, the audit log contains the *events*. To rebuild state, we actually just need to inject them into the bus.
        # However, serializing back to dataclass from JSON dict is needed.
        # Let's import the events we care about for accounting replay.
        from gqos.risk.events import TradeExecutedEvent
        from gqos.accounting.events import (
            PositionOpenedEvent, PositionAdjustedEvent, PositionClosedEvent,
            RealizedPnLEmittedEvent, FeeChargedEvent
        )
        
        event_registry = {
            "TradeExecutedEvent": TradeExecutedEvent,
            "PositionOpenedEvent": PositionOpenedEvent,
            "PositionAdjustedEvent": PositionAdjustedEvent,
            "PositionClosedEvent": PositionClosedEvent,
            "RealizedPnLEmittedEvent": RealizedPnLEmittedEvent,
            "FeeChargedEvent": FeeChargedEvent
        }
        
        with open(self.filepath, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                
                # 1. Verify Hash Chain
                entry_copy = entry.copy()
                recorded_hash = entry_copy.pop("hash")
                
                # Reconstruct JSON identically (sort_keys=True)
                entry_str = json.dumps(entry_copy, sort_keys=True)
                computed_hash = hashlib.sha256(entry_str.encode('utf-8')).hexdigest()
                
                if computed_hash != recorded_hash:
                    raise ValueError(f"Hash mismatch at sequence {entry['sequence']}")
                    
                if entry['previous_hash'] != last_hash:
                    raise ValueError(f"Chain broken at sequence {entry['sequence']}")
                    
                last_hash = computed_hash
                
                # 2. Replay State
                event_type = entry['event_type']
                payload_dict = entry['payload']
                
                if event_type in event_registry:
                    EventClass = event_registry[event_type]
                    # Convert dict values back to appropriate types (e.g. Decimal, Enum)
                    for k, v in payload_dict.items():
                        if isinstance(v, str) and "." in v and v.replace(".", "").isdigit():
                            payload_dict[k] = Decimal(v)
                        # We also need to handle TradeDirection Enum
                        if k == "direction" and isinstance(v, int):
                            payload_dict[k] = TradeDirection(v)
                    
                    try:
                        evt_obj = EventClass(**payload_dict)
                        # We don't need to re-publish TradeExecutedEvent to bus because that would re-trigger 
                        # accounting logic. Instead, we can just apply the primitive accounting events.
                        # Actually, if we just publish TradeExecutedEvent, the AccountingEngine will process it.
                        if event_type == "TradeExecutedEvent":
                            envelope = MessageEnvelope.create(evt_obj, version=1)
                            self.bus.publish(envelope)
                    except Exception as e:
                        pass # Ignore parsing errors for irrelevant fields
                        
        return last_hash
