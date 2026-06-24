from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
import hashlib
import json

@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.Series
    trade_log: pd.DataFrame
    metrics: Dict[str, float]
    
    def calculate_hash(self) -> str:
        # Deterministic hash of the equity curve
        eq_hash = hashlib.sha256(pd.util.hash_pandas_object(self.equity_curve).values).hexdigest()
        metrics_hash = hashlib.sha256(json.dumps(self.metrics, sort_keys=True).encode('utf-8')).hexdigest()
        
        return hashlib.sha256(f"{eq_hash}_{metrics_hash}".encode('utf-8')).hexdigest()

def calculate_backtest_metrics(equity_curve: pd.Series, risk_free_rate: float = 0.0) -> Dict[str, float]:
    """
    Lightweight internal math for performance metrics.
    Assumes equity_curve is daily for annualized calculations, or can be adjusted.
    For simulation, we use simple math.
    """
    if len(equity_curve) < 2:
        return {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}
        
    returns = equity_curve.pct_change().dropna()
    
    # Total Return
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0
    
    # Sharpe Ratio (Assuming daily data, annualization factor 252)
    # If the simulation is minute bars, annualization factor is 252 * 6.5 * 60 approx 98280
    # For a generalized metric in M15, we just use a default 252 factor.
    mean_ret = returns.mean()
    std_ret = returns.std()
    
    if std_ret > 0:
        sharpe = (mean_ret - (risk_free_rate / 252)) / std_ret * np.sqrt(252)
    else:
        sharpe = 0.0
        
    # Max Drawdown
    cumulative_max = equity_curve.cummax()
    drawdown = (equity_curve - cumulative_max) / cumulative_max
    max_drawdown = drawdown.min()
    
    return {
        "total_return": float(total_return),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_drawdown)
    }
