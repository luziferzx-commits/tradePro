from abc import ABC, abstractmethod
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

class IProbabilityCalibrator(ABC):
    @abstractmethod
    def fit(self, predictions: np.ndarray, y_true: np.ndarray):
        pass

    @abstractmethod
    def calibrate(self, predictions: np.ndarray) -> np.ndarray:
        pass

class PlattScaling(IProbabilityCalibrator):
    def __init__(self):
        self.model = LogisticRegression()
        
    def fit(self, predictions: np.ndarray, y_true: np.ndarray):
        # reshape for sklearn
        self.model.fit(predictions.reshape(-1, 1), y_true)
        
    def calibrate(self, predictions: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(predictions.reshape(-1, 1))[:, 1]

class IsotonicCalibration(IProbabilityCalibrator):
    def __init__(self):
        self.model = IsotonicRegression(out_of_bounds='clip')
        
    def fit(self, predictions: np.ndarray, y_true: np.ndarray):
        self.model.fit(predictions, y_true)
        
    def calibrate(self, predictions: np.ndarray) -> np.ndarray:
        return self.model.predict(predictions)
