from typing import Dict, Any
from gqos.alpha.models import ForecastResult

class PortfolioExplainability:
    @staticmethod
    def explain_portfolio_weight(portfolio_weights: Dict[str, float], alpha_forecasts: Dict[str, ForecastResult]) -> Dict[str, Any]:
        """
        Creates a hierarchical explanation: Portfolio -> Alpha -> Feature.
        Shows exactly why the portfolio holds its current aggregate position.
        """
        explanation = {
            "Total_Portfolio_Exposure": 0.0,
            "Alphas": {}
        }
        
        total_exposure = 0.0
        
        for alpha_id, weight in portfolio_weights.items():
            if alpha_id not in alpha_forecasts:
                continue
                
            forecast = alpha_forecasts[alpha_id]
            # Get latest forecast
            latest_row = forecast.frame.iloc[-1]
            score = latest_row["score"]
            f_id = latest_row.name if "forecast_id" not in latest_row else latest_row["forecast_id"]
            
            exposure_contribution = score * weight
            total_exposure += exposure_contribution
            
            alpha_exp = {
                "weight": weight,
                "score": score,
                "exposure_contribution": exposure_contribution,
                "features": {}
            }
            
            # Extract feature-level explanations if available
            if forecast.explanations and f_id in forecast.explanations.store:
                features = forecast.explanations.store[f_id]
                # Scale feature importance by portfolio weight
                alpha_exp["features"] = {k: v * weight for k, v in features.items()}
                
            explanation["Alphas"][alpha_id] = alpha_exp
            
        explanation["Total_Portfolio_Exposure"] = total_exposure
        return explanation
