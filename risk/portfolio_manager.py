import logging
from config.settings import settings
import MetaTrader5 as mt5

logger = logging.getLogger("GoldBot.PortfolioManager")

CORRELATION_GROUPS = {
    "Group_1": ["EURUSDm", "GBPUSDm", "USDJPYm", "EURUSD", "GBPUSD", "USDJPY"],
    "Group_2": ["US30m", "USTECm", "US500m", "US30", "NAS100", "SPX500"],
    "Group_3": ["XAUUSDm", "XAGUSDm", "XAUUSD", "XAGUSD"],
    "Group_4": ["BTCUSDm", "ETHUSDm", "BTCUSD", "ETHUSD"]
}

class PortfolioManager:
    @staticmethod
    def get_symbol_group(symbol):
        for group_name, symbols in CORRELATION_GROUPS.items():
            if symbol in symbols:
                return group_name
        return "Ungrouped"
        
    @staticmethod
    def can_open_trade(symbol, risk_pct):
        """
        Checks if the portfolio can accept a new trade based on constraints.
        Returns (approved: bool, reason: str)
        """
        if not settings.MULTI_MARKET["enabled"]:
            return True, "Multi-market not enabled, skipping portfolio checks."
            
        positions = mt5.positions_get()
        if positions is None:
            logger.warning("Could not retrieve MT5 positions.")
            return False, "Failed to retrieve MT5 positions."
            
        our_positions = [p for p in positions if p.magic == settings.MAGIC_NUMBER]
        
        # Rule 1: Max Open Trades
        max_trades = settings.MULTI_MARKET.get("max_open_trades", 5)
        if len(our_positions) >= max_trades:
            return False, f"Portfolio risk exceeded: max open trades ({max_trades}) reached."
            
        # Rule 2: Max 1 Trade Per Symbol
        symbol_positions = [p for p in our_positions if p.symbol == symbol]
        if len(symbol_positions) >= 1:
            return False, f"Symbol risk exceeded: already have open position for {symbol}."
            
        # Rule 3: Total Open Risk
        # We estimate open risk by assuming each trade risks RISK_PER_TRADE_PCT roughly, or we calculate exact.
        # For simplicity, let's assume each trade is risking what was allowed. 
        # But we don't have exact sl_points here. We will use a rough estimate: len(our_positions) * max_risk_per_trade
        current_est_risk = sum(0.01 for p in our_positions) # Assume 1% per trade for now
        max_total_risk = settings.MULTI_MARKET.get("max_total_open_risk", 0.03)
        if (current_est_risk + risk_pct) > max_total_risk:
            return False, f"Portfolio risk exceeded: total open risk would exceed {max_total_risk*100}%."
            
        # Rule 4: Correlation Filter
        target_group = PortfolioManager.get_symbol_group(symbol)
        if target_group != "Ungrouped":
            group_trades = [p for p in our_positions if PortfolioManager.get_symbol_group(p.symbol) == target_group]
            max_correlated = 2 # Hardcoded requirement
            if len(group_trades) >= max_correlated:
                return False, f"Correlation limit exceeded: already have {max_correlated} trades in {target_group}."
                
        return True, "Approved"

portfolio_manager = PortfolioManager()
