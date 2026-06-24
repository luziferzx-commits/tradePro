from typing import List, Dict, Callable
import numpy as np
import pandas as pd

from gqos.research.factory.generators import TemplateAlpha
from gqos.research.factory.evaluator import VectorizedEvaluator, DeflatedSharpeRatio
from gqos.research.ml.registry import ChampionChallengerRegistry

class CorrelationFilter:
    @staticmethod
    def filter(alphas: List[TemplateAlpha], returns_map: Dict[str, pd.Series], max_correlation: float = 0.5) -> List[TemplateAlpha]:
        """
        Simplified correlation filter. In full production, this would use MST
        or Hierarchical Clustering. Here, we incrementally build a low-correlation pool.
        """
        if not alphas:
            return []
            
        survivors = [alphas[0]]
        
        for alpha in alphas[1:]:
            ret_a = returns_map[alpha.alpha_id]
            
            is_uncorrelated = True
            for survivor in survivors:
                ret_b = returns_map[survivor.alpha_id]
                # Pearson correlation
                corr = ret_a.corr(ret_b)
                if abs(corr) > max_correlation:
                    is_uncorrelated = False
                    break
                    
            if is_uncorrelated:
                survivors.append(alpha)
                
        return survivors

class AlphaTournament:
    def __init__(self, evaluator: VectorizedEvaluator, registry: ChampionChallengerRegistry):
        self.evaluator = evaluator
        self.registry = registry
        
    def run_tournament(self, candidates: List[TemplateAlpha], signal_generator: Callable[[TemplateAlpha], pd.Series], max_correlation: float = 0.5, top_n: int = 10) -> List[TemplateAlpha]:
        """
        Runs the full tournament pipeline:
        1. Evaluate all candidates via vectorization
        2. Calculate DSR
        3. Rank by DSR
        4. Apply Correlation Filter
        5. Auto-Promote Top N to Challenger
        """
        metrics_map = {}
        returns_map = {}
        trial_sharpes = []
        
        # 1. Screen
        for alpha in candidates:
            signals = signal_generator(alpha)
            metrics = self.evaluator.evaluate(signals)
            metrics_map[alpha.alpha_id] = metrics
            returns_map[alpha.alpha_id] = signals * self.evaluator.returns
            trial_sharpes.append(metrics["sharpe"])
            
        # 2. Compute DSR
        for alpha in candidates:
            m = metrics_map[alpha.alpha_id]
            dsr = DeflatedSharpeRatio.calculate(
                m["sharpe"],
                trial_sharpes,
                m["skew"],
                m["kurtosis"],
                m["sample_size"]
            )
            m["dsr"] = dsr
            
        # 3. Rank
        ranked = sorted(candidates, key=lambda a: metrics_map[a.alpha_id]["dsr"], reverse=True)
        
        # 4. Correlation Filter
        uncorrelated = CorrelationFilter.filter(ranked, returns_map, max_correlation)
        
        # 5. Top N
        winners = uncorrelated[:top_n]
        
        # 6. Auto Promotion (Challenger ONLY)
        for rank, alpha in enumerate(winners):
            self.registry.register_challenger(
                alpha_id=alpha.alpha_id,
                strategy_id=alpha.template_name,
                metadata={
                    "rank": rank + 1,
                    "dsr": metrics_map[alpha.alpha_id]["dsr"],
                    "sharpe": metrics_map[alpha.alpha_id]["sharpe"],
                    "parameters": alpha.parameters
                }
            )
            
        return winners
