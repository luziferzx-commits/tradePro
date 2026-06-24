from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Tuple
from datetime import datetime
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.accounting.events import RealizedPnLEmittedEvent, FeeChargedEvent
from gqos.risk.events import TradeExecutedEvent
from gqos.market_data.security_master import ISecurityMaster

@dataclass
class CashFlow:
    timestamp: datetime
    amount: Decimal

@dataclass
class NavSnapshot:
    timestamp: datetime
    nav: Decimal

@dataclass
class AttributionState:
    realized_pnl_by_strategy: Dict[str, Decimal] = field(default_factory=dict)
    realized_pnl_by_symbol: Dict[str, Decimal] = field(default_factory=dict)
    realized_pnl_by_sector: Dict[str, Decimal] = field(default_factory=dict)
    total_realized_pnl: Decimal = Decimal('0')
    total_fees_paid: Decimal = Decimal('0')
    total_slippage: Decimal = Decimal('0')
    
    cash_flows: List[CashFlow] = field(default_factory=list)
    nav_snapshots: List[NavSnapshot] = field(default_factory=list)

@dataclass(frozen=True)
class ReturnMetrics:
    twr: Decimal
    mwr: Decimal

class PerformanceAttributionEngine:
    def __init__(self, event_bus: IEventBus, security_master: ISecurityMaster):
        self._state = AttributionState()
        self._security_master = security_master
        
        event_bus.subscribe(RealizedPnLEmittedEvent, self._on_realized_pnl)
        event_bus.subscribe(FeeChargedEvent, self._on_fee_charged)
        event_bus.subscribe(TradeExecutedEvent, self._on_trade_executed)
        
    @property
    def state(self) -> AttributionState:
        return self._state
        
    def _on_realized_pnl(self, envelope: MessageEnvelope):
        event: RealizedPnLEmittedEvent = envelope.payload
        pnl = event.realized_pnl
        
        self._state.total_realized_pnl += pnl
        
        # Strategy
        self._state.realized_pnl_by_strategy[event.strategy_id] = self._state.realized_pnl_by_strategy.get(event.strategy_id, Decimal('0')) + pnl
        
        # Symbol
        self._state.realized_pnl_by_symbol[event.symbol] = self._state.realized_pnl_by_symbol.get(event.symbol, Decimal('0')) + pnl
        
        # Sector
        sector = self._security_master.get_sector(event.symbol)
        self._state.realized_pnl_by_sector[sector] = self._state.realized_pnl_by_sector.get(sector, Decimal('0')) + pnl
        
    def _on_fee_charged(self, envelope: MessageEnvelope):
        event: FeeChargedEvent = envelope.payload
        self._state.total_fees_paid += event.amount
        
    def _on_trade_executed(self, envelope: MessageEnvelope):
        event: TradeExecutedEvent = envelope.payload
        if event.slippage_amount is not None:
            self._state.total_slippage += event.slippage_amount
            
    def record_cash_flow(self, timestamp: datetime, amount: Decimal):
        self._state.cash_flows.append(CashFlow(timestamp, amount))
        
    def record_nav_snapshot(self, timestamp: datetime, nav: Decimal):
        self._state.nav_snapshots.append(NavSnapshot(timestamp, nav))
        
    def calculate_twr(self) -> Decimal:
        """
        Time-Weighted Return neutralizes the impact of external cash flows.
        It links sub-period returns exactly at the points of cash flows.
        For M10C, we assume NavSnapshots are taken immediately BEFORE cash flows.
        R_i = (NAV_end - NAV_start - CashFlow) / NAV_start
        """
        if len(self._state.nav_snapshots) < 2:
            return Decimal('0')
            
        snapshots = sorted(self._state.nav_snapshots, key=lambda x: x.timestamp)
        cash_flows = sorted(self._state.cash_flows, key=lambda x: x.timestamp)
        
        # Simple TWR over predefined snapshots:
        # TWR = product(1 + R_i) - 1
        twr_product = Decimal('1.0')
        
        for i in range(1, len(snapshots)):
            start_nav = snapshots[i-1].nav
            end_nav = snapshots[i].nav
            
            if start_nav == Decimal('0'):
                continue
                
            # Find cash flows in this period (excluding start, including end)
            period_cfs = [cf.amount for cf in cash_flows if snapshots[i-1].timestamp < cf.timestamp <= snapshots[i].timestamp]
            total_cf = sum(period_cfs, Decimal('0'))
            
            # Assuming cash flows occur exactly after the start snapshot (at the beginning of the sub-period)
            adjusted_start_nav = start_nav + total_cf
            if adjusted_start_nav == Decimal('0'):
                period_return = Decimal('0')
            else:
                period_return = (end_nav - start_nav - total_cf) / adjusted_start_nav
                
            twr_product *= (Decimal('1.0') + period_return)
            
        return twr_product - Decimal('1.0')

    def calculate_mwr(self) -> Decimal:
        """
        Money-Weighted Return (Modified Dietz Method).
        R = (NAV_end - NAV_start - Total_CF) / (NAV_start + sum(CF_i * W_i))
        Where W_i is the proportion of the period remaining.
        """
        if len(self._state.nav_snapshots) < 2:
            return Decimal('0')
            
        snapshots = sorted(self._state.nav_snapshots, key=lambda x: x.timestamp)
        cash_flows = sorted(self._state.cash_flows, key=lambda x: x.timestamp)
        
        start_snapshot = snapshots[0]
        end_snapshot = snapshots[-1]
        
        bmv = start_snapshot.nav
        emv = end_snapshot.nav
        
        total_days = Decimal((end_snapshot.timestamp - start_snapshot.timestamp).total_seconds() / 86400.0)
        if total_days <= Decimal('0'):
            return Decimal('0')
            
        total_cf = Decimal('0')
        weighted_cf = Decimal('0')
        
        for cf in cash_flows:
            if start_snapshot.timestamp <= cf.timestamp <= end_snapshot.timestamp:
                total_cf += cf.amount
                days_remaining = Decimal((end_snapshot.timestamp - cf.timestamp).total_seconds() / 86400.0)
                weight = days_remaining / total_days
                weighted_cf += (cf.amount * weight)
                
        denominator = bmv + weighted_cf
        if denominator == Decimal('0'):
            return Decimal('0')
            
        return (emv - bmv - total_cf) / denominator
