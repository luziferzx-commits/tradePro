import pandas as pd
import numpy as np

class FeatureDriftDetectedEvent:
    def __init__(self, feature_id: str, p_value: float, metric_name: str, message: str):
        self.feature_id = feature_id
        self.p_value = p_value
        self.metric_name = metric_name
        self.message = message
        
    def __str__(self):
        return f"[DRIFT DETECTED] {self.feature_id}: {self.metric_name} p-value={self.p_value:.4f}. {self.message}"

class FeatureDriftDetector:
    """
    Telemetry-only detector that alerts if the out-of-sample feature distribution
    deviates significantly from the in-sample distribution.
    """
    def __init__(self, p_value_threshold: float = 0.05):
        self.p_value_threshold = p_value_threshold
        self._events = []
        
    def detect_mean_shift(self, feature_id: str, baseline: pd.Series, oos: pd.Series):
        """
        Simple Welch's t-test approximation for mean shift.
        Emits FeatureDriftDetectedEvent if shift is significant.
        """
        # Drop NaNs
        base_clean = baseline.dropna()
        oos_clean = oos.dropna()
        
        if len(base_clean) < 2 or len(oos_clean) < 2:
            return
            
        m1, m2 = base_clean.mean(), oos_clean.mean()
        v1, v2 = base_clean.var(ddof=1), oos_clean.var(ddof=1)
        n1, n2 = len(base_clean), len(oos_clean)
        
        # Welch's t-statistic
        se = np.sqrt(v1/n1 + v2/n2)
        if se == 0:
            return
            
        t_stat = (m1 - m2) / se
        
        # Approximate p-value (assuming large N, normal approx)
        # Using a very basic rough check since scipy is not guaranteed available in all minimal environments
        # A t-stat > 1.96 roughly corresponds to p < 0.05
        # We will map standard normal CDF roughly.
        # For simplicity in this mock, we just use a heuristic based on t_stat
        p_val = np.exp(-0.717 * t_stat - 0.416 * t_stat**2) if t_stat > 0 else np.exp(0.717 * t_stat - 0.416 * t_stat**2)
        
        if p_val < self.p_value_threshold:
            event = FeatureDriftDetectedEvent(
                feature_id=feature_id,
                p_value=p_val,
                metric_name="MeanShift",
                message=f"In-sample mean {m1:.4f} shifted to OOS mean {m2:.4f}"
            )
            self._events.append(event)
            
    def get_events(self) -> list:
        return self._events
