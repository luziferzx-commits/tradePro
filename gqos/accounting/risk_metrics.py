from dataclasses import dataclass
from decimal import Decimal
from typing import List, Tuple
from datetime import datetime, timedelta
import math
from gqos.accounting.attribution import NavSnapshot
from gqos.accounting.events import RealizedPnLEmittedEvent
from gqos.risk.events import TradeExecutedEvent

@dataclass(frozen=True)
class DrawdownMetrics:
    max_drawdown_pct: Decimal
    max_duration: timedelta

class RiskMetricsEngine:
    def __init__(self, annualization_factor: int = 252):
        self.annualization_factor = annualization_factor

    def _compute_returns(self, snapshots: List[NavSnapshot]) -> List[Decimal]:
        if len(snapshots) < 2:
            return []
        
        sorted_snaps = sorted(snapshots, key=lambda x: x.timestamp)
        returns = []
        for i in range(1, len(sorted_snaps)):
            prev_nav = sorted_snaps[i-1].nav
            curr_nav = sorted_snaps[i].nav
            if prev_nav == Decimal('0'):
                returns.append(Decimal('0'))
            else:
                returns.append((curr_nav - prev_nav) / prev_nav)
        return returns

    def _annualize_return(self, returns: List[Decimal]) -> Decimal:
        if not returns:
            return Decimal('0')
        # product of (1+r) - 1, then annualized
        # Alternatively, average daily return * annualization_factor
        # We will use compound annualization if we assume each return is daily.
        # But a safer approach for irregular intervals is (End/Start)^(annualization/len) - 1
        # Given we want basic stats:
        avg_ret = sum(returns) / Decimal(len(returns))
        return avg_ret * Decimal(self.annualization_factor)

    def calculate_drawdown(self, snapshots: List[NavSnapshot]) -> DrawdownMetrics:
        if not snapshots:
            return DrawdownMetrics(Decimal('0'), timedelta(0))

        sorted_snaps = sorted(snapshots, key=lambda x: x.timestamp)
        max_dd = Decimal('0')
        peak_nav = sorted_snaps[0].nav
        peak_time = sorted_snaps[0].timestamp
        
        max_duration = timedelta(0)
        
        for snap in sorted_snaps:
            if snap.nav > peak_nav:
                peak_nav = snap.nav
                peak_time = snap.timestamp
            else:
                if peak_nav > Decimal('0'):
                    dd = (peak_nav - snap.nav) / peak_nav
                    if dd > max_dd:
                        max_dd = dd
                
                duration = snap.timestamp - peak_time
                if duration > max_duration:
                    max_duration = duration

        return DrawdownMetrics(max_drawdown_pct=max_dd, max_duration=max_duration)

    def calculate_sharpe_ratio(self, snapshots: List[NavSnapshot], risk_free_rate: Decimal = Decimal('0')) -> Decimal:
        returns = self._compute_returns(snapshots)
        if not returns:
            return Decimal('0')
            
        avg_ret = sum(returns) / Decimal(len(returns))
        
        variance = sum((r - avg_ret)**2 for r in returns) / Decimal(len(returns))
        std_dev = Decimal(math.sqrt(float(variance)))
        
        if std_dev == Decimal('0'):
            return Decimal('0') # Zero volatility handling
            
        annualized_return = avg_ret * Decimal(self.annualization_factor)
        annualized_volatility = std_dev * Decimal(math.sqrt(self.annualization_factor))
        
        return (annualized_return - risk_free_rate) / annualized_volatility

    def calculate_sortino_ratio(self, snapshots: List[NavSnapshot], risk_free_rate: Decimal = Decimal('0'), target_return: Decimal = Decimal('0')) -> Decimal:
        returns = self._compute_returns(snapshots)
        if not returns:
            return Decimal('0')
            
        avg_ret = sum(returns) / Decimal(len(returns))
        
        downside_returns = [r - target_return for r in returns if r < target_return]
        
        if not downside_returns:
            return Decimal('0') # Zero downside deviation handling
            
        downside_variance = sum(r**2 for r in downside_returns) / Decimal(len(returns))
        downside_dev = Decimal(math.sqrt(float(downside_variance)))
        
        if downside_dev == Decimal('0'):
            return Decimal('0')
            
        annualized_return = avg_ret * Decimal(self.annualization_factor)
        annualized_downside_volatility = downside_dev * Decimal(math.sqrt(self.annualization_factor))
        
        return (annualized_return - risk_free_rate) / annualized_downside_volatility

    def calculate_calmar_ratio(self, snapshots: List[NavSnapshot], risk_free_rate: Decimal = Decimal('0')) -> Decimal:
        returns = self._compute_returns(snapshots)
        if not returns:
            return Decimal('0')
            
        avg_ret = sum(returns) / Decimal(len(returns))
        annualized_return = avg_ret * Decimal(self.annualization_factor)
        
        dd_metrics = self.calculate_drawdown(snapshots)
        
        if dd_metrics.max_drawdown_pct == Decimal('0'):
            return Decimal('0') # Zero drawdown handling
            
        return (annualized_return - risk_free_rate) / dd_metrics.max_drawdown_pct

    def calculate_rolling_profit_factor(self, pnl_events: List[Tuple[datetime, Decimal]], window_days: int = 30) -> Decimal:
        """
        Calculates the Profit Factor over a rolling time window ending at the latest event.
        pnl_events: list of tuples (timestamp, realized_pnl)
        """
        if not pnl_events:
            return Decimal('0')
            
        sorted_events = sorted(pnl_events, key=lambda x: x[0])
        latest_time = sorted_events[-1][0]
        cutoff_time = latest_time - timedelta(days=window_days)
        
        gross_profit = Decimal('0')
        gross_loss = Decimal('0')
        
        for t, pnl in sorted_events:
            if t >= cutoff_time:
                if pnl > Decimal('0'):
                    gross_profit += pnl
                elif pnl < Decimal('0'):
                    gross_loss += abs(pnl)
                    
        if gross_loss == Decimal('0'):
            return Decimal('99999.0') if gross_profit > Decimal('0') else Decimal('0') # Zero-loss case handling
            
        return gross_profit / gross_loss
