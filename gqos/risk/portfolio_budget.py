import logging
import json
import os
from collections import defaultdict, deque
from typing import Dict

logger = logging.getLogger("GQOS.PortfolioBudget")

class PortfolioBudgetManager:
    """
    Dynamic Risk Allocation:
    Adjusts the risk multiplier based on symbol performance.
    
    WR > 60%  -> 1.25x
    40-60%    -> 1.00x
    30-40%    -> 0.50x
    < 30%     -> 0.25x
    
    If WR < 30% and trades >= 20 -> 0x (Pause Trading)
    """

    def __init__(
        self,
        pending_trades_path: str = "data/learning/pending_trades.json",
        loss_pause_usd: float = -150.0,
    ):
        self.pending_trades_path = pending_trades_path
        self.loss_pause_usd = loss_pause_usd
        self.stats: Dict[str, Dict] = defaultdict(
            lambda: {'w': 0, 'l': 0, 'pnl': 0.0, 'recent': deque(maxlen=5)}
        )
        self._load_stats_from_mt5()

    def _load_stats_from_mt5(self):
        """Load history from MT5 to compute win rate per symbol."""
        try:
            import MetaTrader5 as mt5
            from datetime import datetime, timedelta
            if not mt5.initialize():
                logger.warning("MT5 initialize failed for PortfolioBudgetManager")
                return

            # Rolling intraday window: stats reset at the start of the current
            # day rather than being anchored to a hard-coded date that has to be
            # bumped by hand. Override with GQOS_BUDGET_LOOKBACK_DAYS if a longer
            # window is desired.
            try:
                lookback_days = int(os.getenv("GQOS_BUDGET_LOOKBACK_DAYS", "0"))
            except (TypeError, ValueError):
                lookback_days = 0
            if lookback_days > 0:
                start = datetime.now() - timedelta(days=lookback_days)
            else:
                start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            deals = mt5.history_deals_get(start, datetime.now()) or []
            closed = sorted(
                [d for d in deals if d.entry == 1 and d.profit != 0],
                key=lambda d: getattr(d, "time", 0),
            )

            for d in closed:
                sym = d.symbol
                pnl = float(d.profit)
                if d.profit > 0:
                    self.stats[sym]['w'] += 1
                else:
                    self.stats[sym]['l'] += 1
                self.stats[sym]['pnl'] += pnl
                self.stats[sym]['recent'].append(pnl)
            logger.info("PortfolioBudgetManager: Loaded stats from MT5 history.")
        except Exception as e:
            logger.error(f"PortfolioBudgetManager failed to load stats: {e}")

    def get_multiplier(self, symbol: str) -> float:
        """Calculate the risk multiplier for the given symbol."""
        s = self.stats.get(symbol)
        if not s:
            return 1.0 # Default if no history
            
        wins = s['w']
        losses = s['l']
        total = wins + losses
        pnl = float(s.get('pnl', 0.0))
        recent = list(s.get('recent', []))
        
        if total == 0:
            return 1.0
            
        wr = wins / total

        # Fast live damage control. Do not wait for 20 trades when a symbol is
        # already causing material realized damage or has a fresh loss streak.
        if pnl <= self.loss_pause_usd and total >= 3:
            logger.warning(
                "[PortfolioBudget] %s paused: realized pnl %.2f over %s trades",
                symbol,
                pnl,
                total,
            )
            return 0.0

        if len(recent) >= 3 and all(x < 0 for x in recent[-3:]):
            logger.warning(
                "[PortfolioBudget] %s paused: last 3 closed trades are losses",
                symbol,
            )
            return 0.0

        if wr < 0.35 and total >= 5:
            logger.warning(
                "[PortfolioBudget] %s paused: win rate %.1f%% over %s trades",
                symbol,
                wr * 100,
                total,
            )
            return 0.0
        
        # Cut (Pause Trading) if statistically significant underperformance
        if wr < 0.30 and total >= 20:
            return 0.0
            
        if wr > 0.60:
            return 1.25
        elif 0.40 <= wr <= 0.60:
            return 1.00
        elif 0.30 <= wr < 0.40:
            return 0.50
        else:
            return 0.25

    def get_all_multipliers(self) -> Dict[str, Dict]:
        """Returns a dict of all symbols with their stats and multipliers."""
        result = {}
        for sym, s in self.stats.items():
            wins = s['w']
            losses = s['l']
            total = wins + losses
            wr = wins / total if total > 0 else 0.0
            mult = self.get_multiplier(sym)
            status = 'PAUSED' if mult == 0.0 else 'ACTIVE'
            
            result[sym] = {
                'win_rate': wr,
                'multiplier': mult,
                'trades': total,
                'pnl': round(float(s.get('pnl', 0.0)), 2),
                'recent': list(s.get('recent', [])),
                'status': status
            }
        return result

portfolio_budget = PortfolioBudgetManager()
