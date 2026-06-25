import math
import hashlib
from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_EVEN
from typing import Optional
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, SizingResult, RoundingPolicy, InvalidSizingRequestError
from gqos.sizing.portfolio import PortfolioSnapshot

def apply_rounding(quantity: Decimal, policy: RoundingPolicy, precision: Decimal = Decimal('0.01')) -> Decimal:
    if policy == RoundingPolicy.ROUND_DOWN:
        return quantity.quantize(precision, rounding=ROUND_DOWN)
    elif policy == RoundingPolicy.ROUND_UP:
        return quantity.quantize(precision, rounding=ROUND_UP)
    elif policy == RoundingPolicy.BANKERS:
        return quantity.quantize(precision, rounding=ROUND_HALF_EVEN)
    else:
        return quantity

class ISizingPolicy(ABC):
    @property
    @abstractmethod
    def policy_name(self) -> str: pass
    
    @property
    @abstractmethod
    def policy_version(self) -> str: pass
    
    @property
    @abstractmethod
    def policy_parameters_hash(self) -> str: pass

    @abstractmethod
    def calculate_size(self, request: SizingRequest, portfolio: PortfolioSnapshot) -> SizingResult:
        pass

class FixedFractionalPolicy(ISizingPolicy):
    def __init__(self, fraction: Decimal, rounding: RoundingPolicy = RoundingPolicy.ROUND_DOWN, max_position_value: Optional[Decimal] = None):
        if not (Decimal('0') < fraction <= Decimal('1')):
            raise ValueError("Fraction must be between 0 and 1 exclusive")
        self.fraction = fraction
        self.rounding = rounding
        self.max_position_value = max_position_value
        
    @property
    def policy_name(self) -> str: return "FixedFractional"
    @property
    def policy_version(self) -> str: return "1.1"
    @property
    def policy_parameters_hash(self) -> str:
        return hashlib.md5(f"{self.fraction}_{self.rounding}_{self.max_position_value}".encode()).hexdigest()
        
    def calculate_size(self, request: SizingRequest, portfolio: PortfolioSnapshot) -> SizingResult:
        capital_to_use = portfolio.total_equity * self.fraction
        
        if self.max_position_value is not None:
            capital_to_use = min(capital_to_use, self.max_position_value)
            
        raw_quantity = capital_to_use / request.entry_price
        
        quantity = apply_rounding(raw_quantity, self.rounding)
        estimated_value = quantity * request.entry_price
        
        reason = f"FixedFractional(fraction={self.fraction}): Equity={portfolio.total_equity} -> TargetValue={capital_to_use} -> RawQty={raw_quantity} -> Qty={quantity}"
        
        if quantity <= Decimal('0'):
            print(f"DEBUG SIZING: {reason}")
            raise InvalidSizingRequestError(f"Calculated quantity is zero or negative. Details: {reason}")
            
        return SizingResult(
            quantity=quantity,
            estimated_value=estimated_value,
            risk_amount=estimated_value,
            capital_used=estimated_value,
            sizing_reason=reason
        )

class FixedRiskPolicy(ISizingPolicy):
    def __init__(self, risk_fraction: Decimal, rounding: RoundingPolicy = RoundingPolicy.ROUND_DOWN):
        if not (Decimal('0') < risk_fraction <= Decimal('1')):
            raise ValueError("Risk fraction must be between 0 and 1 exclusive")
        self.risk_fraction = risk_fraction
        self.rounding = rounding
        
    @property
    def policy_name(self) -> str: return "FixedRisk"
    @property
    def policy_version(self) -> str: return "1.0"
    @property
    def policy_parameters_hash(self) -> str:
        return hashlib.md5(f"{self.risk_fraction}_{self.rounding}".encode()).hexdigest()
        
    def calculate_size(self, request: SizingRequest, portfolio: PortfolioSnapshot) -> SizingResult:
        if request.stop_loss_price is None:
            raise InvalidSizingRequestError("FixedRiskPolicy requires a stop_loss_price")
            
        if request.entry_price == request.stop_loss_price:
            raise InvalidSizingRequestError("Entry price and Stop Loss price cannot be identical")
            
        if request.direction == TradeDirection.BUY and request.stop_loss_price >= request.entry_price:
            raise InvalidSizingRequestError("For BUY, stop_loss_price must be below entry_price")
            
        if request.direction == TradeDirection.SELL and request.stop_loss_price <= request.entry_price:
            raise InvalidSizingRequestError("For SELL, stop_loss_price must be above entry_price")
            
        loss_per_share = abs(request.entry_price - request.stop_loss_price)
        risk_amount = portfolio.total_equity * self.risk_fraction
        
        raw_quantity = risk_amount / loss_per_share
        quantity = apply_rounding(raw_quantity, self.rounding)
        
        if quantity <= Decimal('0'):
            raise InvalidSizingRequestError("Calculated quantity is zero or negative.")
            
        estimated_value = quantity * request.entry_price
        
        reason = f"FixedRisk(fraction={self.risk_fraction}): RiskAmount={risk_amount}, LossPerShare={loss_per_share} -> RawQty={raw_quantity} -> Qty={quantity}"
        
        return SizingResult(
            quantity=quantity,
            estimated_value=estimated_value,
            risk_amount=quantity * loss_per_share,
            capital_used=estimated_value,
            sizing_reason=reason
        )

class KellyPolicy(ISizingPolicy):
    def __init__(self, fractional_multiplier: Decimal = Decimal('1.0'), rounding: RoundingPolicy = RoundingPolicy.ROUND_DOWN, max_kelly_fraction: Optional[Decimal] = Decimal('0.2')):
        """
        Fractional Kelly. Defaults to Full Kelly (1.0).
        Half-Kelly = 0.5. Quarter-Kelly = 0.25.
        max_kelly_fraction limits the maximum percentage of equity to risk/allocate on a single trade.
        """
        if fractional_multiplier <= Decimal('0'):
            raise ValueError("fractional_multiplier must be > 0")
        self.fractional_multiplier = fractional_multiplier
        self.rounding = rounding
        self.max_kelly_fraction = max_kelly_fraction
        
    @property
    def policy_name(self) -> str: return "KellyCriterion"
    @property
    def policy_version(self) -> str: return "1.0"
    @property
    def policy_parameters_hash(self) -> str:
        return hashlib.md5(f"{self.fractional_multiplier}_{self.rounding}_{self.max_kelly_fraction}".encode()).hexdigest()
        
    def calculate_size(self, request: SizingRequest, portfolio: PortfolioSnapshot) -> SizingResult:
        if request.metrics is None:
            raise InvalidSizingRequestError("KellyPolicy requires StrategyMetrics in SizingRequest")
            
        w = request.metrics.win_rate
        r = request.metrics.win_loss_ratio
        
        if not (Decimal('0') < w < Decimal('1')):
            raise InvalidSizingRequestError("Win rate (W) must be strictly between 0 and 1")
            
        if r <= Decimal('0'):
            raise InvalidSizingRequestError("Win/Loss Ratio (R) must be > 0")
            
        # K = W - ((1 - W) / R)
        kelly_fraction = w - ((Decimal('1') - w) / r)
        
        if kelly_fraction <= Decimal('0'):
            raise InvalidSizingRequestError(f"Calculated Kelly fraction is negative or zero: {kelly_fraction}. Trade should not be taken.")
            
        adjusted_kelly = kelly_fraction * self.fractional_multiplier
        
        if self.max_kelly_fraction is not None:
            adjusted_kelly = min(adjusted_kelly, self.max_kelly_fraction)
            
        capital_to_use = portfolio.total_equity * adjusted_kelly
        raw_quantity = capital_to_use / request.entry_price
        
        quantity = apply_rounding(raw_quantity, self.rounding)
        
        if quantity <= Decimal('0'):
            raise InvalidSizingRequestError("Calculated quantity is zero or negative after rounding.")
            
        estimated_value = quantity * request.entry_price
        
        reason = (f"KellyPolicy(W={w}, R={r}): KellyFraction={kelly_fraction} -> "
                  f"Adjusted(x{self.fractional_multiplier}, max={self.max_kelly_fraction})={adjusted_kelly} -> "
                  f"Capital={capital_to_use} -> RawQty={raw_quantity} -> Qty={quantity}")
                  
        return SizingResult(
            quantity=quantity,
            estimated_value=estimated_value,
            risk_amount=estimated_value, # True risk depends on stop loss, but here Kelly treats capital allocated as risk
            capital_used=estimated_value,
            sizing_reason=reason
        )

class VolatilityRiskPolicy(ISizingPolicy):
    def __init__(self, risk_fraction: Decimal, atr_multiplier: Decimal, rounding: RoundingPolicy = RoundingPolicy.ROUND_DOWN):
        if not (Decimal('0') < risk_fraction <= Decimal('1')):
            raise ValueError("risk_fraction must be between 0 and 1 exclusive")
        if atr_multiplier <= Decimal('0'):
            raise ValueError("atr_multiplier must be > 0")
            
        self.risk_fraction = risk_fraction
        self.atr_multiplier = atr_multiplier
        self.rounding = rounding
        
    @property
    def policy_name(self) -> str: return "VolatilityRisk"
    @property
    def policy_version(self) -> str: return "1.0"
    @property
    def policy_parameters_hash(self) -> str:
        return hashlib.md5(f"{self.risk_fraction}_{self.atr_multiplier}_{self.rounding}".encode()).hexdigest()
        
    def calculate_size(self, request: SizingRequest, portfolio: PortfolioSnapshot) -> SizingResult:
        if request.volatility is None or request.volatility.atr is None:
            raise InvalidSizingRequestError("VolatilityRiskPolicy requires VolatilityMetrics with ATR")
            
        atr = request.volatility.atr
        if atr <= Decimal('0'):
            raise InvalidSizingRequestError("ATR must be > 0")
            
        dynamic_stop = None
        stop_loss_price = request.stop_loss_price
        
        if stop_loss_price is None:
            if request.direction == TradeDirection.BUY:
                stop_loss_price = request.entry_price - (atr * self.atr_multiplier)
            else:
                stop_loss_price = request.entry_price + (atr * self.atr_multiplier)
            dynamic_stop = stop_loss_price
            
        loss_per_share = abs(request.entry_price - stop_loss_price)
        if loss_per_share == Decimal('0'):
            raise InvalidSizingRequestError("Entry price and Stop Loss price cannot be identical")
            
        risk_amount = portfolio.total_equity * self.risk_fraction
        raw_quantity = risk_amount / loss_per_share
        
        quantity = apply_rounding(raw_quantity, self.rounding)
        
        if quantity <= Decimal('0'):
            raise InvalidSizingRequestError("Calculated quantity is zero or negative.")
            
        estimated_value = quantity * request.entry_price
        
        reason = (f"VolatilityRisk(risk={self.risk_fraction}, atr_mult={self.atr_multiplier}): "
                  f"ATR={atr} -> RiskAmount={risk_amount}, LossPerShare={loss_per_share} -> "
                  f"RawQty={raw_quantity} -> Qty={quantity}")
                  
        return SizingResult(
            quantity=quantity,
            estimated_value=estimated_value,
            risk_amount=quantity * loss_per_share,
            capital_used=estimated_value,
            sizing_reason=reason,
            dynamic_stop_loss=dynamic_stop
        )

class VolatilityTargetPolicy(ISizingPolicy):
    def __init__(self, target_annual_volatility: Decimal, rounding: RoundingPolicy = RoundingPolicy.ROUND_DOWN):
        if target_annual_volatility <= Decimal('0'):
            raise ValueError("target_annual_volatility must be > 0")
            
        self.target_annual_volatility = target_annual_volatility
        self.rounding = rounding
        
    @property
    def policy_name(self) -> str: return "VolatilityTarget"
    @property
    def policy_version(self) -> str: return "1.0"
    @property
    def policy_parameters_hash(self) -> str:
        return hashlib.md5(f"{self.target_annual_volatility}_{self.rounding}".encode()).hexdigest()
        
    def calculate_size(self, request: SizingRequest, portfolio: PortfolioSnapshot) -> SizingResult:
        if request.volatility is None or request.volatility.annualized_volatility is None:
            raise InvalidSizingRequestError("VolatilityTargetPolicy requires VolatilityMetrics with annualized_volatility")
            
        asset_vol = request.volatility.annualized_volatility
        if asset_vol <= Decimal('0'):
            raise InvalidSizingRequestError("Asset annualized volatility must be > 0")
            
        # Target sizing formula
        capital_to_use = portfolio.total_equity * (self.target_annual_volatility / asset_vol)
        raw_quantity = capital_to_use / request.entry_price
        
        quantity = apply_rounding(raw_quantity, self.rounding)
        
        if quantity <= Decimal('0'):
            raise InvalidSizingRequestError("Calculated quantity is zero or negative.")
            
        estimated_value = quantity * request.entry_price
        
        reason = (f"VolatilityTarget(target_vol={self.target_annual_volatility}): "
                  f"AssetVol={asset_vol} -> CapitalTarget={capital_to_use} -> "
                  f"RawQty={raw_quantity} -> Qty={quantity}")
                  
        return SizingResult(
            quantity=quantity,
            estimated_value=estimated_value,
            risk_amount=estimated_value,
            capital_used=estimated_value,
            sizing_reason=reason
        )
