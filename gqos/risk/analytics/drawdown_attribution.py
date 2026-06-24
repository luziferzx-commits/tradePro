from decimal import Decimal
from typing import Dict
from gqos.market_data.security_master import ISecurityMaster
from gqos.risk.analytics.models import DrawdownAttributionResult

class DrawdownAttributionEngine:
    def calculate_drawdown_attribution(
        self, 
        peak_symbol_equity: Dict[str, Decimal], 
        trough_symbol_equity: Dict[str, Decimal],
        symbol_to_strategy: Dict[str, str],
        security_master: ISecurityMaster
    ) -> DrawdownAttributionResult:
        """
        Calculates attribution of a drawdown using the delta in Total Equity (Realized + Unrealized)
        between the Peak timestamp and the Trough timestamp.
        """
        total_drawdown_amount = Decimal('0')
        contribution_by_strategy: Dict[str, Decimal] = {}
        contribution_by_sector: Dict[str, Decimal] = {}
        contribution_by_symbol: Dict[str, Decimal] = {}

        # Get all symbols that existed at peak or trough
        all_symbols = set(peak_symbol_equity.keys()).union(set(trough_symbol_equity.keys()))
        
        peak_total_equity = sum(peak_symbol_equity.values())

        for symbol in all_symbols:
            peak_eq = peak_symbol_equity.get(symbol, Decimal('0'))
            trough_eq = trough_symbol_equity.get(symbol, Decimal('0'))
            
            # Drawdown contribution is Peak Equity - Trough Equity
            delta = peak_eq - trough_eq
            total_drawdown_amount += delta
            
            # Accumulate Symbol
            contribution_by_symbol[symbol] = delta
            
            # Accumulate Strategy
            strategy = symbol_to_strategy.get(symbol, "UNKNOWN")
            contribution_by_strategy[strategy] = contribution_by_strategy.get(strategy, Decimal('0')) + delta
            
            # Accumulate Sector
            sector = security_master.get_sector(symbol)
            contribution_by_sector[sector] = contribution_by_sector.get(sector, Decimal('0')) + delta

        # Drawdown percent
        total_drawdown_percent = Decimal('0')
        if peak_total_equity > Decimal('0'):
            total_drawdown_percent = total_drawdown_amount / peak_total_equity

        return DrawdownAttributionResult(
            total_drawdown_amount=total_drawdown_amount,
            total_drawdown_percent=total_drawdown_percent,
            contribution_by_strategy=contribution_by_strategy,
            contribution_by_sector=contribution_by_sector,
            contribution_by_symbol=contribution_by_symbol
        )
