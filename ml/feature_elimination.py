import os
import pandas as pd
import numpy as np
import xgboost as xgb
import shap
from typing import Dict, List, Tuple
from gqos.research.ml.validation import CombinatorialPurgedCV
from gqos.research.ml.explainability import FeatureImportance
from sklearn.metrics import accuracy_score
import warnings

warnings.filterwarnings('ignore')

class FeatureEliminator:
    def __init__(self, data_path: str):
        self.df = pd.read_csv(data_path)
        self.features = [
            "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
            "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
            "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
        ]
        self.features = [f for f in self.features if f in self.df.columns]
        
        # Base model (the "stable" one found in Phase 3)
        self.base_model = xgb.XGBClassifier(
            max_depth=2, learning_rate=0.01, n_estimators=100, subsample=0.9,
            random_state=42, eval_metric='logloss', n_jobs=-1
        )
        
        # Setup CPCV
        n_samples = len(self.df)
        purge_candles = 10
        embargo_candles = 200
        self.cpcv = CombinatorialPurgedCV(
            n_groups=6, k_test_groups=2, 
            purge_pct=purge_candles/n_samples, 
            embargo_pct=embargo_candles/n_samples
        )

    def compute_mda_and_shap(self):
        print("--- Running MDA & SHAP Engine ---")
        X = self.df[self.features]
        y = self.df['label']
        
        splits = list(self.cpcv.split(self.df))
        num_splits = len(splits)
        
        # Storage
        mda_scores = {f: [] for f in self.features}
        shap_values_dict = {f: [] for f in self.features}
        interaction_matrices = []
        feature_ranks_per_fold = []
        oos_pfs = []
        
        print(f"Total CV Paths: {num_splits}")
        
        for i, (train_idx, test_idx) in enumerate(splits):
            X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
            X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
            df_test = self.df.iloc[test_idx]
            
            if len(y_train) < 50 or len(X_test) == 0:
                continue
                
            model = xgb.XGBClassifier(**self.base_model.get_params())
            model.fit(X_train, y_train)
            
            # 1. Base Accuracy for MDA
            preds = model.predict(X_test)
            base_acc = accuracy_score(y_test, preds)
            
            # PF for this fold
            trades_mask = preds == 1
            trades_df = df_test[trades_mask]
            if not trades_df.empty:
                wins = trades_df[trades_df['result_r'] > 0]['result_r'].sum()
                losses = abs(trades_df[trades_df['result_r'] <= 0]['result_r'].sum())
                pf = wins / losses if losses > 0 else 1.0
            else:
                pf = 0.0
            oos_pfs.append(pf)
            
            # 2. MDA calculation
            fold_mda = {}
            for col in self.features:
                X_permuted = X_test.copy()
                X_permuted[col] = np.random.permutation(X_permuted[col].values)
                permuted_preds = model.predict(X_permuted)
                drop = base_acc - accuracy_score(y_test, permuted_preds)
                mda_scores[col].append(drop)
                fold_mda[col] = drop
                
            # Rank features by MDA in this fold
            sorted_mda = sorted(fold_mda.items(), key=lambda x: x[1], reverse=True)
            ranks = {feat: rank for rank, (feat, _) in enumerate(sorted_mda)}
            feature_ranks_per_fold.append(ranks)
            
            # 3. SHAP Calculation (TreeExplainer)
            explainer = shap.TreeExplainer(model, feature_perturbation="tree_path_dependent")
            shap_vals = explainer.shap_values(X_test)
            
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]
            elif len(shap_vals.shape) == 3:
                shap_vals = shap_vals[:, :, 1]
                
            for j, col in enumerate(self.features):
                shap_values_dict[col].extend(shap_vals[:, j])
                
            # 4. SHAP Interaction
            try:
                # TreeExplainer supports shap_interaction_values for xgboost
                interact_vals = explainer.shap_interaction_values(X_test)
                if isinstance(interact_vals, list):
                    interact_vals = interact_vals[1]
                mean_abs_interact = np.abs(interact_vals).mean(axis=0)
                interaction_matrices.append(mean_abs_interact)
            except Exception as e:
                pass
                
        self.mda_scores = {k: np.mean(v) for k, v in mda_scores.items()}
        self.shap_values = {k: np.array(v) for k, v in shap_values_dict.items()}
        self.oos_pfs = oos_pfs
        self.feature_ranks_per_fold = feature_ranks_per_fold
        
        if interaction_matrices:
            self.mean_interaction = np.mean(interaction_matrices, axis=0)
        else:
            self.mean_interaction = None

    def calculate_s_score(self) -> Dict[str, dict]:
        print("\n--- Calculating Composite Stability Score (S) ---")
        # S = 0.4 * SHAP_consistency + 0.3 * OOS_PF_variance_inv + 0.2 * fold_rank_stability + 0.1 * feature_rank_correlation
        
        results = {}
        
        # OOS PF Variance component (Global for the model)
        # We invert it: lower variance -> higher score
        pf_var = np.var(self.oos_pfs)
        # Normalize: if variance > 1.0, score = 0
        pf_var_score = max(0, 1.0 - pf_var) 
        
        for j, feat in enumerate(self.features):
            # 1. SHAP Consistency (Directional agreement)
            shaps = self.shap_values[feat]
            if len(shaps) == 0:
                results[feat] = {"S": 0, "status": "KILL"}
                continue
                
            # % of shap values that have the same sign as the mean shap value
            mean_shap = np.mean(shaps)
            if mean_shap == 0:
                shap_consistency = 0.0
            else:
                sign = np.sign(mean_shap)
                agreement = np.sum(np.sign(shaps) == sign) / len(shaps)
                shap_consistency = agreement # max 1.0, min 0.0
                
            # 2. Fold Rank Stability
            # Variance of the feature's rank across folds
            ranks = [fold[feat] for fold in self.feature_ranks_per_fold]
            mean_rank = np.mean(ranks)
            max_rank = len(self.features) - 1
            # Normalize rank variance
            rank_var = np.var(ranks)
            rank_stability = max(0, 1.0 - (rank_var / (max_rank**2 / 4))) # heuristic normalization
            
            # 3. Feature Rank Correlation (Spearman across folds)
            # Simplified: just use rank stability as a proxy for correlation consistency
            feat_corr = rank_stability 
            
            # 4. Interaction Trap Detector
            is_dependent = False
            if self.mean_interaction is not None:
                # Diagonal is main effect, off-diagonal is interaction
                main_effect = self.mean_interaction[j, j]
                interaction_sum = np.sum(self.mean_interaction[j, :]) - main_effect
                if interaction_sum > main_effect * 1.5: # Arbitrary threshold for "dependent"
                    is_dependent = True
            
            # Composite S
            s_score = 0.4 * shap_consistency + 0.3 * pf_var_score + 0.2 * rank_stability + 0.1 * feat_corr
            
            # 3-Layer Kill Logic
            mda = self.mda_scores[feat]
            shap_var = np.std(shaps)
            
            classification = "UNKNOWN"
            
            # HARD KILL
            if mda <= 0 and abs(mean_shap) < 1e-4 and s_score < 0.2:
                classification = "HARD_KILL"
            # WEAK SIGNAL
            elif mda > 0 and (shap_var > 0.5 or shap_consistency < 0.6):
                classification = "WEAK_SIGNAL"
            # KEEP
            elif mda > 0 and shap_consistency >= 0.7 and rank_stability > 0.5:
                classification = "KEEP"
            else:
                # Catch-all
                if s_score >= 0.75:
                    classification = "KEEP"
                elif s_score >= 0.5:
                    classification = "WEAK_SIGNAL"
                else:
                    classification = "HARD_KILL"
                    
            if is_dependent:
                classification += "_DEPENDENT"

            results[feat] = {
                "MDA": float(mda),
                "SHAP_mean": float(mean_shap),
                "SHAP_consistency": float(shap_consistency),
                "S_Score": float(s_score),
                "Classification": classification
            }
            
            print(f"{feat:25} | MDA: {mda:.4f} | S: {s_score:.2f} | Class: {classification}")
            
        return results

if __name__ == "__main__":
    import glob
    files = glob.glob("datasets/*/*.csv")
    if not files:
        files = glob.glob("datasets/*.csv")
        
    data_file = files[-1]
    for f in files:
        if "XAUUSDm" in f:
            data_file = f
            break
            
    eliminator = FeatureEliminator(data_file)
    eliminator.compute_mda_and_shap()
    results = eliminator.calculate_s_score()
    
    # Save partial results
    import json
    os.makedirs("ml/temp", exist_ok=True)
    with open("ml/temp/feature_elimination_results.json", "w") as f:
        json.dump(results, f, indent=4)
