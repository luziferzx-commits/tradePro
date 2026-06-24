import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass

from gqos.alpha.models import IAlphaModel, ForecastResult
from gqos.alpha.validation.metrics import AlphaValidationMetrics
from gqos.alpha.validation.matrix import AlphaMatrix

@dataclass
class AlphaEvaluationProfile:
    alpha_id: str
    ic_mean: float
    rank_ic_mean: float
    ic_stability: float
    turnover: float
    signal_density: float
    objective_score: float

class WalkForwardRanker:
    def __init__(self, folds: int = 5):
        self.folds = folds
        
    def _calculate_objective(self, rank_ic: float, stability: float, turnover: float) -> float:
        """
        Deterministic ranking objective.
        Weights: 50% Rank IC, 30% Stability, -20% Turnover Penalty
        """
        # Penalize extremely high turnover
        turnover_penalty = min(turnover, 0.5) * 2.0 
        return (rank_ic * 0.5) + (min(stability, 2.0) * 0.15) - (turnover_penalty * 0.2)

    def evaluate(self, models: Dict[str, pd.Series], price_df: pd.DataFrame, method: str = "open_to_close") -> List[AlphaEvaluationProfile]:
        """
        Simulates walk-forward evaluation by calculating ICs over the dataset.
        For simplicity in this framework, we split the dataset into `self.folds` chunks.
        """
        profiles = []
        
        # Split prices into folds
        chunk_size = len(price_df) // self.folds
        if chunk_size < 10:
            raise ValueError("Dataset too small for 5-fold walk forward")
            
        for alpha_id, forecasts in models.items():
            ic_list = []
            rank_ic_list = []
            turnovers = []
            densities = []
            
            for i in range(self.folds):
                start = i * chunk_size
                # the last fold takes the remainder
                end = (i + 1) * chunk_size if i < self.folds - 1 else len(price_df)
                
                fold_prices = price_df.iloc[start:end]
                fold_forecasts = forecasts.iloc[start:end]
                
                fwd_ret = AlphaValidationMetrics.generate_forward_returns(fold_prices, method=method)
                
                # Metrics
                ic = AlphaValidationMetrics.calculate_ic(fold_forecasts, fwd_ret)
                rank_ic = AlphaValidationMetrics.calculate_rank_ic(fold_forecasts, fwd_ret)
                
                # Turnover
                turn = float(fold_forecasts.diff().abs().mean()) if len(fold_forecasts) > 1 else 0.0
                # Density
                dens = float((fold_forecasts.abs() > 0.05).sum() / len(fold_forecasts)) if len(fold_forecasts) > 0 else 0.0
                
                ic_list.append(ic)
                rank_ic_list.append(rank_ic)
                turnovers.append(turn)
                densities.append(dens)
                
            ic_series = pd.Series(ic_list)
            rank_ic_series = pd.Series(rank_ic_list)
            
            ic_mean = float(ic_series.mean())
            rank_ic_mean = float(rank_ic_series.mean())
            stability = AlphaValidationMetrics.calculate_ic_stability(rank_ic_series)
            
            turnover_mean = float(np.mean(turnovers))
            density_mean = float(np.mean(densities))
            
            objective = self._calculate_objective(rank_ic_mean, stability, turnover_mean)
            
            profiles.append(AlphaEvaluationProfile(
                alpha_id=alpha_id,
                ic_mean=ic_mean,
                rank_ic_mean=rank_ic_mean,
                ic_stability=stability,
                turnover=turnover_mean,
                signal_density=density_mean,
                objective_score=objective
            ))
            
        # Rank descending
        profiles.sort(key=lambda x: x.objective_score, reverse=True)
        return profiles

class ChampionChallengerFramework:
    def __init__(self, corr_threshold: float = 0.7):
        self.corr_threshold = corr_threshold
        self.champions: Dict[str, pd.Series] = {}
        self.rejection_log: List[Dict[str, Any]] = []
        
    def evaluate_challenger(self, alpha_id: str, forecast: pd.Series, allow_orthogonalization: bool = False) -> bool:
        """
        Evaluates a candidate.
        Returns True if accepted, False if rejected.
        """
        if not self.champions:
            self.champions[alpha_id] = forecast
            return True
            
        # Check correlations
        correlations = {}
        max_corr = 0.0
        most_correlated_champion = None
        
        for champ_id, champ_forecast in self.champions.items():
            df = pd.concat([forecast, champ_forecast], axis=1).fillna(0.0)
            if len(df) > 1:
                corr = abs(df.iloc[:, 0].corr(df.iloc[:, 1], method='spearman'))
                correlations[champ_id] = corr
                if corr > max_corr:
                    max_corr = corr
                    most_correlated_champion = champ_id
                    
        if max_corr > self.corr_threshold:
            if allow_orthogonalization and most_correlated_champion is not None:
                # Orthogonalize
                champ_forecast = self.champions[most_correlated_champion]
                ortho_forecast = AlphaMatrix.orthogonalize(forecast, champ_forecast)
                self.champions[f"{alpha_id}_ortho"] = ortho_forecast
                
                self.rejection_log.append({
                    "alpha_id": alpha_id,
                    "status": "ACCEPTED_ORTHOGONALIZED",
                    "reason": f"Correlation {max_corr:.2f} > {self.corr_threshold} with {most_correlated_champion}. Orthogonalized."
                })
                return True
            else:
                self.rejection_log.append({
                    "alpha_id": alpha_id,
                    "status": "REJECTED",
                    "reason": f"Correlation {max_corr:.2f} > {self.corr_threshold} with {most_correlated_champion}"
                })
                return False
                
        # Accept
        self.champions[alpha_id] = forecast
        return True
