# gqos.alpha.validation

from gqos.alpha.models import ForecastResult

class ForecastValidationError(Exception):
    pass

class ForecastValidator:
    @staticmethod
    def validate(result: ForecastResult):
        df = result.frame
        
        # Check score bounds [-1, 1]
        if not df["score"].between(-1.0, 1.0).all():
            raise ForecastValidationError("Scores must be between -1.0 and 1.0")
            
        # Check confidence bounds [0, 1]
        if not df["confidence"].between(0.0, 1.0).all():
            raise ForecastValidationError("Confidence must be between 0.0 and 1.0")
            
        # Check quality bounds [0, 1]
        if not df["quality"].between(0.0, 1.0).all():
            raise ForecastValidationError("Quality must be between 0.0 and 1.0")
            
        # Check that forecast_id exists
        if "forecast_id" not in df.columns:
            raise ForecastValidationError("ForecastFrame missing 'forecast_id'")