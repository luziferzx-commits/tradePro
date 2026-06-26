import os
code = """
import json
import os

class DynamicScalingPolicy(ISizingPolicy):
    def __init__(self, base_risk_fraction: Decimal, rounding: RoundingPolicy = RoundingPolicy.ROUND_DOWN):
        if not (Decimal('0') < base_risk_fraction <= Decimal('1')):
            raise ValueError("Risk fraction must be between 0 and 1 exclusive")
        self.base_risk_fraction = base_risk_fraction
        self.rounding = rounding
        self.state_file = "data/learning/dynamic_scaling_state.json"
        self._load_state()
        
    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self.max_equity = Decimal(str(data.get("max_equity", 0)))
            except:
                self.max_equity = Decimal('0')
        else:
            self.max_equity = Decimal('0')
            
    def _save_state(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump({"max_equity": float(self.max_equity)}, f)
            
    @property
    def policy_name(self) -> str: return "DynamicScaling"
    
    @property
    def policy_version(self) -> str: return "1.0"
    
    @property
    def policy_parameters_hash(self) -> str:
        return hashlib.md5(f"{self.base_risk_fraction}_{self.rounding}".encode()).hexdigest()
        
    def calculate_size(self, request: SizingRequest, portfolio: PortfolioSnapshot) -> SizingResult:
        if request.stop_loss_price is None:
            raise InvalidSizingRequestError("DynamicScalingPolicy requires a stop_loss_price")
            
        current_equity = portfolio.total_equity
        if current_equity > self.max_equity:
            self.max_equity = current_equity
            self._save_state()
            
        # 1. Calculate Drawdown
        drawdown = Decimal('0')
        if self.max_equity > 0:
            drawdown = (self.max_equity - current_equity) / self.max_equity
            
        # Circuit Breaker
        if drawdown > Decimal('0.10'):
            raise InvalidSizingRequestError(f"Circuit Breaker Triggered: Drawdown {drawdown*100:.2f}% > 10%")
            
        # 2. Calculate Win Streak
        from gqos.learning.outcome_logger import outcome_logger
        df = outcome_logger.get_outcomes_df()
        win_streak = 0
        if not df.empty:
            recent_trades = df.sort_values("close_time", ascending=False)
            for _, row in recent_trades.iterrows():
                if row.get('pnl', 0) > 0:
                    win_streak += 1
                else:
                    break
                    
        # 3. Determine dynamic risk
        if win_streak >= 5:
            dynamic_risk = Decimal('0.015')
        elif drawdown > Decimal('0.05'):
            dynamic_risk = Decimal('0.005')
        else:
            dynamic_risk = self.base_risk_fraction
            
        # 4. Standard FixedRisk Calculation using dynamic_risk
        loss_per_share = abs(request.entry_price - request.stop_loss_price)
        risk_amount = current_equity * dynamic_risk
        
        import MetaTrader5 as mt5
        info = mt5.symbol_info(request.symbol)
        
        if info and info.trade_tick_size > 0 and info.trade_tick_value > 0:
            tick_size = Decimal(str(info.trade_tick_size))
            tick_value = Decimal(str(info.trade_tick_value))
            risk_per_lot = (loss_per_share / tick_size) * tick_value
            raw_quantity = risk_amount / risk_per_lot if risk_per_lot > 0 else risk_amount / loss_per_share
        else:
            raw_quantity = risk_amount / loss_per_share
            
        quantity = apply_rounding(raw_quantity, self.rounding)
        
        if quantity <= Decimal('0'):
            raise InvalidSizingRequestError("Calculated quantity is zero or negative.")
            
        estimated_value = quantity * request.entry_price
        reason = (f"DynamicScaling(base={self.base_risk_fraction}, actual={dynamic_risk}): "
                  f"DD={drawdown*100:.2f}%, Streak={win_streak} -> Qty={quantity}")
                  
        return SizingResult(
            quantity=quantity,
            estimated_value=estimated_value,
            risk_amount=quantity * loss_per_share,
            capital_used=estimated_value,
            sizing_reason=reason
        )
"""
with open("gqos/sizing/policies.py", "a") as f:
    f.write("\n" + code)
