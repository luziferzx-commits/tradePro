"""portfolio/capital_allocator.py"""
import logging
from market.market_metadata import MarketMetadata
from portfolio.correlation_engine import CorrelationEngine
from portfolio.exposure_manager import ExposureManager
from risk.portfolio_drawdown_guard import PortfolioDrawdownGuard

logger = logging.getLogger(__name__)

class CapitalAllocator:
    def __init__(self, 
                 metadata: MarketMetadata, 
                 correlation_engine: CorrelationEngine, 
                 exposure_manager: ExposureManager,
                 base_risk_pct: float = 0.01,
                 account_balance: float = 500.0):
        self.metadata = metadata
        self.correlation = correlation_engine
        self.exposure = exposure_manager
        self.base_risk_pct = base_risk_pct
        self.account_balance = account_balance
        
    def allocate(self, ranked_opportunities: list[dict], open_positions: list[dict]) -> tuple[list[dict], list[dict]]:
        executions = []
        rejections = []
        
        # 1. Check Portfolio Drawdown Guard First
        is_safe, dd_reason = PortfolioDrawdownGuard.is_safe()
        if not is_safe:
            logger.warning(f"PORTFOLIO_DD_GUARD_TRIGGERED: {dd_reason}")
            for opp in ranked_opportunities:
                opp['reject_reason'] = "PORTFOLIO_DD_GUARD_TRIGGERED"
                rejections.append(opp)
            return executions, rejections
        
        simulated_positions = list(open_positions)
        
        for opp in ranked_opportunities:
            symbol = opp.get('symbol')
            side = opp.get('side')
            
            # 1. Calculate Correlation Penalty
            corr_multiplier, reduction_reasons = self.correlation.calculate_correlation_penalty(symbol, side, simulated_positions)
            
            if corr_multiplier <= 0.01:
                opp['reject_reason'] = "100% Correlated Risk (Redundant)"
                rejections.append(opp)
                continue
                
            # 2. Adjust Risk Size
            allocated_risk_pct = self.base_risk_pct * corr_multiplier
            
            # 3. Check Exposure Limits
            allowed, reason = self.exposure.check_exposure_limits(symbol, allocated_risk_pct, simulated_positions)
            
            if not allowed:
                opp['reject_reason'] = reason
                rejections.append(opp)
                continue
                
            # 4. Lot Feasibility Check
            risk_amount_money = self.account_balance * allocated_risk_pct
            
            sym_meta = self.metadata.registry.get_symbol(symbol)
            if not sym_meta:
                opp['reject_reason'] = f"Missing symbol metadata for {symbol}"
                rejections.append(opp)
                continue
                
            min_lot = sym_meta.get('min_lot', 0.01)
            max_lot = sym_meta.get('max_lot', 100.0)
            lot_step = sym_meta.get('lot_step', 0.01)
            tick_value = sym_meta.get('tick_value', 1.0)
            
            # Assume a standardized stop loss distance for estimation (e.g., typical spread * 5)
            assumed_stop_points = sym_meta.get('typical_spread_points', 20) * 5
            if assumed_stop_points == 0:
                assumed_stop_points = 20
                
            raw_lot = risk_amount_money / (assumed_stop_points * tick_value)
            
            # Round to lot step
            estimated_lot = max(min_lot, round(raw_lot / lot_step) * lot_step)
            
            if estimated_lot > max_lot:
                estimated_lot = max_lot
                
            # If we bumped to min_lot, check if the NEW risk exceeds limits
            if estimated_lot > raw_lot:
                actual_risk_money = estimated_lot * assumed_stop_points * tick_value
                actual_risk_pct = actual_risk_money / self.account_balance
                allowed, reason = self.exposure.check_exposure_limits(symbol, actual_risk_pct, simulated_positions)
                if not allowed:
                    opp['reject_reason'] = f"Min lot bump ({min_lot}) causes risk breach: {reason}"
                    rejections.append(opp)
                    continue
                allocated_risk_pct = actual_risk_pct
                
            execution_order = dict(opp)
            execution_order['risk_amount_pct'] = allocated_risk_pct
            execution_order['correlation_multiplier'] = corr_multiplier
            execution_order['reduction_reasons'] = reduction_reasons
            execution_order['estimated_lot'] = estimated_lot
            
            executions.append(execution_order)
            
            simulated_positions.append({
                'symbol': symbol,
                'side': side,
                'risk_amount_pct': allocated_risk_pct
            })
            
        return executions, rejections
