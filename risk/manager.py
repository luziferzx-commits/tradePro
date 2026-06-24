import logging
import MetaTrader5 as mt5
from config.settings import settings

logger = logging.getLogger(__name__)

class RiskManager:
    @staticmethod
    def calculate_position_size(symbol: str, sl_points: float, ml_prob: float = 0.0, memory_sim: float = 0.0, health_score: int = 100) -> float:
        """
        Calculates dynamic position size based on V6.1 Bayesian Quarter-Kelly criteria.
        Risk is strictly capped at 1.00%.
        """
        account_info = mt5.account_info()
        if not account_info:
            logger.error("Failed to get account info for position sizing")
            return 0.0
            
        balance = account_info.balance
        
        # Bayesian Win Rate Adjustment
        p = ml_prob
        
        # Adjust based on System Health only (Systemic risk)
        if health_score < 80:
            p -= 0.05
            
        p = max(0.01, min(0.99, p))
        b = 2.5 # Target RR
        
        # Kelly Criterion calculation
        f_star = p - ((1.0 - p) / b)
        
        if f_star <= 0:
            logger.warning(f"Negative Expected Value (EV). Kelly suggests 0 risk. (p={p:.2f})")
            return 0.0
            
        # Quarter-Kelly
        risk_pct = f_star / 4.0
        
        # Strict max risk cap
        risk_pct = min(risk_pct, 0.01) # Max 1.00%
        
        logger.info(f"Bayesian Quarter-Kelly: {risk_pct*100:.2f}% (p={p:.2f}, sim={memory_sim:.2f}, health={health_score})")
        
        risk_amount = balance * risk_pct
        
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"Failed to get symbol info for {symbol}")
            return 0.0
            
        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size
        
        if sl_points <= 0 or tick_value <= 0 or tick_size <= 0:
            return 0.0
            
        # SL in points * point value = risk per lot
        # This is a simplified calculation, adjust according to actual symbol specs
        point = symbol_info.point
        loss_per_lot = (sl_points * point) * (tick_value / tick_size)
        
        if loss_per_lot <= 0:
            return 0.0
            
        lots = risk_amount / loss_per_lot
        
        # Round to nearest allowed step
        step = symbol_info.volume_step
        min_vol = symbol_info.volume_min
        max_vol = symbol_info.volume_max
        
        # Round properly downwards to avoid exceeding risk
        lots = (lots // step) * step
        
        # Safely truncate floating point precision
        lots = round(lots, 2)
        
        if lots < min_vol:
            logger.warning(f"Calculated lots ({lots}) below minimum volume ({min_vol}). Trade rejected.")
            return 0.0
        if lots > max_vol:
            logger.warning(f"Calculated lots ({lots}) above maximum volume ({max_vol}). Capping to max_vol.")
            lots = max_vol
            
        return lots
