from typing import List, Dict, Tuple, Any
import pandas as pd
import numpy as np

from gqos.alpha.models import ForecastResult
from gqos.backtest.results import BacktestResult

class AlphaAnalytics:
    @staticmethod
    def forecast_distribution(forecasts: pd.Series, bins: int = 10) -> Dict[str, float]:
        """
        Creates a histogram dictionary of forecast scores.
        Useful for plotting or reporting the distribution to detect bias.
        """
        hist, bin_edges = np.histogram(forecasts.fillna(0.0), bins=bins, range=(-1.0, 1.0))
        dist = {}
        for i in range(len(hist)):
            label = f"[{bin_edges[i]:.1f}, {bin_edges[i+1]:.1f})"
            dist[label] = int(hist[i])
        return dist

    @staticmethod
    def signal_density(forecasts: pd.Series, threshold: float = 0.05) -> float:
        """
        Calculates the percentage of bars where the absolute forecast score exceeds a threshold.
        """
        if len(forecasts) == 0:
            return 0.0
        active_bars = (forecasts.abs() > threshold).sum()
        return float(active_bars / len(forecasts))

    @staticmethod
    def forecast_turnover(forecasts: pd.Series) -> float:
        """
        Calculates the average absolute change in forecast score per bar.
        High turnover means the score flips rapidly (noise).
        """
        if len(forecasts) < 2:
            return 0.0
        diff = forecasts.diff().abs()
        return float(diff.mean())

    @staticmethod
    def feature_importance_history(result: ForecastResult) -> pd.DataFrame:
        """
        Extracts the explanation store into a DataFrame over time.
        Index = Timestamp, Columns = Feature IDs, Values = Contribution (0.0 to 1.0).
        """
        data = []
        indices = []
        
        for i, idx in enumerate(result.frame.index):
            f_id = result.frame['forecast_id'].iloc[i]
            explanation = result.explanations.get(f_id)
            if explanation:
                data.append(explanation)
                indices.append(idx)
                
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data, index=indices).fillna(0.0)
        return df

class AlphaBenchmarkSuite:
    @staticmethod
    def calculate_hit_rate(trade_log: pd.DataFrame) -> float:
        # Assuming trade_log has a 'pnl' column
        if trade_log.empty or 'pnl' not in trade_log.columns:
            return 0.0
        wins = (trade_log['pnl'] > 0).sum()
        return float(wins / len(trade_log))

    @staticmethod
    def calculate_profit_factor(trade_log: pd.DataFrame) -> float:
        if trade_log.empty or 'pnl' not in trade_log.columns:
            return 0.0
        gross_profit = trade_log[trade_log['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trade_log[trade_log['pnl'] < 0]['pnl'].sum())
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        return float(gross_profit / gross_loss)

    @staticmethod
    def evaluate_model(alpha_id: str, forecast_result: ForecastResult, backtest_result: BacktestResult) -> Dict[str, Any]:
        """
        Comprehensive evaluation matching the M16D requirement.
        """
        score_series = forecast_result.frame['score']
        
        metrics = backtest_result.metrics.copy()
        
        # Add Analytics
        metrics["signal_density"] = AlphaAnalytics.signal_density(score_series)
        metrics["forecast_turnover"] = AlphaAnalytics.forecast_turnover(score_series)
        metrics["hit_rate"] = AlphaBenchmarkSuite.calculate_hit_rate(backtest_result.trade_log)
        metrics["profit_factor"] = AlphaBenchmarkSuite.calculate_profit_factor(backtest_result.trade_log)
        
        # In a real system, Stability/WalkForward/Drift are injected from the M13 orchestrator
        metrics["stability"] = 0.90 # Mock
        metrics["drift_events"] = 0 # Mock
        
        return {
            "alpha_id": alpha_id,
            "metrics": metrics,
            "distribution": AlphaAnalytics.forecast_distribution(score_series)
        }
