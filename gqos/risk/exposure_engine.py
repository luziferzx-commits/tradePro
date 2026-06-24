import threading
from typing import Tuple, List
from types import MappingProxyType
from decimal import Decimal
from gqos.risk.events import ExecuteTradeCommand, TradeExecutedEvent
from gqos.risk.exposure import ExposureSnapshot, ExposureLimits, Position
from gqos.risk.assets import AssetDirectory

class ExposureEngine:
    def __init__(self, asset_dir: AssetDirectory, limits: ExposureLimits):
        self._asset_dir = asset_dir
        self._limits = limits
        self._lock = threading.RLock()
        self._snapshot = ExposureSnapshot(version=1, parent_version=0)
        
    def evaluate_trade(self, cmd: ExecuteTradeCommand) -> Tuple[bool, str, str]:
        """
        O(1) Delta-based evaluation of a trade against exposure limits.
        """
        asset = self._asset_dir.get_asset(cmd.symbol)
        if not asset:
            return False, "UNKNOWN_SYMBOL", f"Symbol {cmd.symbol} is not registered in the Asset Directory."
            
        if cmd.quantity == Decimal('0'):
            return True, "", ""
            
        with self._lock:
            # Price estimate
            price = cmd.estimated_value / cmd.quantity
            signed_trade_qty = cmd.quantity * Decimal(cmd.direction.value)
            
            old_pos = self._snapshot.positions.get(cmd.symbol)
            old_gross = old_pos.gross_value if old_pos else Decimal('0')
            old_net = old_pos.net_value if old_pos else Decimal('0')
            
            new_qty = (old_pos.quantity if old_pos else Decimal('0')) + signed_trade_qty
            new_gross = abs(new_qty * price)
            new_net = new_qty * price
            
            gross_delta = new_gross - old_gross
            net_delta = new_net - old_net
            
            proj_gross = self._snapshot.gross_exposure + gross_delta
            proj_net = self._snapshot.net_exposure + net_delta
            proj_sym_gross = old_gross + gross_delta
            proj_sec_gross = self._snapshot.get_sector_gross(asset.sector) + gross_delta
            proj_grp_gross = self._snapshot.get_group_gross(asset.correlation_group) + gross_delta
            
            # Checks
            if proj_gross > self._limits.max_gross_exposure:
                return False, "GROSS_EXPOSURE", f"Projected Gross: {proj_gross} > Limit: {self._limits.max_gross_exposure}"
            
            if abs(proj_net) > self._limits.max_net_exposure:
                return False, "NET_EXPOSURE", f"Projected Net magnitude: {abs(proj_net)} > Limit: {self._limits.max_net_exposure}"
                
            if proj_sym_gross > self._limits.max_symbol_exposure:
                return False, "SYMBOL_EXPOSURE", f"Projected {cmd.symbol} exposure: {proj_sym_gross} > Limit: {self._limits.max_symbol_exposure}"
                
            if proj_sec_gross > self._limits.max_sector_exposure:
                return False, "SECTOR_EXPOSURE", f"Projected Sector '{asset.sector}' exposure: {proj_sec_gross} > Limit: {self._limits.max_sector_exposure}"
                
            if proj_grp_gross > self._limits.max_correlation_group_exposure:
                return False, "CORRELATION_GROUP", f"Projected Group '{asset.correlation_group}' exposure: {proj_grp_gross} > Limit: {self._limits.max_correlation_group_exposure}"
                
            return True, "", ""

    def apply_trade(self, event: TradeExecutedEvent):
        """
        Creates a new immutable ExposureSnapshot.
        """
        with self._lock:
            # M7C.5 Technical Debt: Exposure Version Policy
            # M7C.5 Technical Debt: Shared Delta Logic
            self._snapshot = self._calculate_next_snapshot(self._snapshot, event)

    def _calculate_next_snapshot(self, current_snapshot: ExposureSnapshot, event: TradeExecutedEvent, event_version: int = None) -> ExposureSnapshot:
        asset = self._asset_dir.get_asset(event.symbol)
        if not asset:
            return current_snapshot # Safety check
            
        old_pos = current_snapshot.positions.get(event.symbol)
        old_qty = old_pos.quantity if old_pos else Decimal('0')
        old_avg = old_pos.average_entry_price if old_pos else Decimal('0')
        
        trade_qty = event.quantity * Decimal(event.direction.value)
        price = event.execution_price
        new_qty = old_qty + trade_qty
        
        # Calculate new average entry price
        if new_qty == Decimal('0'):
            new_avg = Decimal('0')
        elif old_qty == Decimal('0'):
            new_avg = price
        else:
            # Same direction (increase)
            if (old_qty > 0 and trade_qty > 0) or (old_qty < 0 and trade_qty < 0):
                total_value = (abs(old_qty) * old_avg) + (abs(trade_qty) * price)
                new_avg = total_value / abs(new_qty)
            # Flip direction
            elif (old_qty > 0 and new_qty < 0) or (old_qty < 0 and new_qty > 0):
                new_avg = price
            # Reduce
            else:
                new_avg = old_avg
                
        # Zero-quantity position removal
        new_positions = dict(current_snapshot.positions)
        
        old_gross = old_pos.gross_value if old_pos else Decimal('0')
        old_net = old_pos.net_value if old_pos else Decimal('0')
        
        if new_qty == Decimal('0'):
            if event.symbol in new_positions:
                del new_positions[event.symbol]
            new_gross = Decimal('0')
            new_net = Decimal('0')
        else:
            new_pos = Position(
                symbol=event.symbol,
                quantity=new_qty,
                average_entry_price=new_avg,
                last_price=price
            )
            new_positions[event.symbol] = new_pos
            new_gross = new_pos.gross_value
            new_net = new_pos.net_value
        
        gross_delta = new_gross - old_gross
        net_delta = new_net - old_net
        
        new_sectors = dict(current_snapshot.sector_exposures)
        new_sectors[asset.sector] = new_sectors.get(asset.sector, Decimal('0')) + gross_delta
        
        new_groups = dict(current_snapshot.group_exposures)
        new_groups[asset.correlation_group] = new_groups.get(asset.correlation_group, Decimal('0')) + gross_delta
        
        # Exposure Version Policy: Use the event's underlying version if available, otherwise just +1 from parent
        new_version = event_version if event_version is not None else getattr(event, 'version', current_snapshot.version + 1)
        
        return ExposureSnapshot(
            version=new_version,
            parent_version=current_snapshot.version,
            gross_exposure=current_snapshot.gross_exposure + gross_delta,
            net_exposure=current_snapshot.net_exposure + net_delta,
            positions=MappingProxyType(new_positions),
            sector_exposures=MappingProxyType(new_sectors),
            group_exposures=MappingProxyType(new_groups)
        )

    def rebuild_from_events(self, events: List):
        """
        Rebuilds the snapshot state from an event stream.
        """
        with self._lock:
            # We don't optimize to O(N) by merging dicts anymore because the Architect
            # explicitly requested Single Source of Truth `_calculate_next_snapshot`.
            # We will rely on Python's MappingProxy creation performance (which is ~50us per event).
            # This is acceptable for rebuilds since they happen only on startup.
            snapshot = ExposureSnapshot(version=1, parent_version=0)
            for env in events:
                if isinstance(env.payload, TradeExecutedEvent):
                    snapshot = self._calculate_next_snapshot(snapshot, env.payload, event_version=env.version)
            self._snapshot = snapshot
