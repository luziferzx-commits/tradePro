import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from sklearn.base import clone
from sklearn.metrics import accuracy_score

from gqos.research.ml.validation import PurgedKFold
from gqos.alpha.models import ForecastResult

class FeatureImportance:
    @staticmethod
    def mean_decrease_accuracy(model, X: pd.DataFrame, y: pd.Series, cv: PurgedKFold) -> pd.Series:
        """
        Calculates Mean Decrease Accuracy (MDA) using PurgedKFold Cross-Validation.
        This prevents leakage and accounts for feature interactions.
        """
        importances = {col: [] for col in X.columns}
        
        for train_idx, test_idx in cv.split(X, y):
            X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
            X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
            
            # Train model
            fold_model = clone(model)
            fold_model.fit(X_train, y_train)
            
            # Base accuracy
            preds = fold_model.predict(X_test)
            base_acc = accuracy_score(y_test, preds)
            
            # Permute each feature and measure drop in accuracy
            for col in X.columns:
                X_test_permuted = X_test.copy()
                X_test_permuted[col] = np.random.permutation(X_test_permuted[col].values)
                
                permuted_preds = fold_model.predict(X_test_permuted)
                permuted_acc = accuracy_score(y_test, permuted_preds)
                
                drop = base_acc - permuted_acc
                importances[col].append(drop)
                
        # Average drops across folds
        mean_importances = {col: np.mean(drops) for col, drops in importances.items()}
        return pd.Series(mean_importances).sort_values(ascending=False)

class SHAPExplainer:
    """
    Optional dependency wrapper for SHAP.
    """
    def __init__(self, model):
        self.model = model
        self.explainer = None
        
    def _init_explainer(self, X: pd.DataFrame):
        try:
            import shap
        except ImportError:
            raise ImportError("shap library is required. Please install with `pip install shap`")
            
        if self.explainer is None:
            # TreeExplainer is fastest for Random Forests / XGBoost
            self.explainer = shap.TreeExplainer(self.model, feature_perturbation="tree_path_dependent")
            
    def explain_forecasts(self, X: pd.DataFrame, result: ForecastResult) -> ForecastResult:
        """
        Calculates SHAP values and attaches them to the ForecastResult ExplanationStore.
        """
        self._init_explainer(X)
        shap_values = self.explainer.shap_values(X)
        
        # If binary classification, shap_values might be a list or a 3D array
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        elif len(shap_values.shape) == 3:
            shap_values = shap_values[:, :, 1]
            
        for i, idx in enumerate(X.index):
            forecast_id = result.frame.iloc[i]['forecast_id']
            explanation = {col: float(shap_values[i, j] if len(shap_values.shape) > 1 else shap_values[j]) for j, col in enumerate(X.columns)}
            result.explanations.add(forecast_id, explanation)
            
        return result
