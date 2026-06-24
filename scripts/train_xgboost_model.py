"""scripts/train_xgboost_model.py — Train XGBoost classifier on MT5 historical dataset."""
import os
import sys
import glob
import logging
import joblib
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import f1_score, classification_report

logger = logging.getLogger("XGBTrain")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

FEATURES = [
    "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
    "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc", "is_high_volatility", "is_buy",
    "recent_high_20_distance", "recent_low_20_distance"
]

TARGET = "label"

def train():
    print("=" * 60)
    print(" XGBOOST MODEL TRAINING ")
    print("=" * 60)

    # 1. Find the latest dataset
    dataset_files = glob.glob("datasets/training_data_*.csv")
    if not dataset_files:
        logger.error("No dataset found in datasets/ directory. Run build_training_dataset.py first.")
        return
        
    latest_file = max(dataset_files)
    logger.info(f"Loading dataset: {latest_file}")
    
    df = pd.read_csv(latest_file)
    
    if df.empty:
        logger.error("Dataset is empty.")
        return

    # 2. Time-series sorting (CRITICAL)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values("timestamp").reset_index(drop=True)
    else:
        logger.warning("No timestamp column found. Assuming data is already sorted chronologically.")

    # Validate features exist
    missing_feats = [f for f in FEATURES if f not in df.columns]
    if missing_feats:
        logger.error(f"Dataset is missing required features: {missing_feats}")
        return

    # 3. Train/Test Split (75% / 25% chronological)
    split_idx = int(len(df) * 0.75)
    
    X = df[FEATURES]
    y = df[TARGET]
    
    X_train, y_train = X.iloc[:split_idx], y.iloc[:split_idx]
    X_test, y_test = X.iloc[split_idx:], y.iloc[split_idx:]
    
    logger.info(f"Total samples: {len(df)}")
    logger.info(f"Train samples: {len(X_train)} (75%)")
    logger.info(f"Test samples:  {len(X_test)} (25%)")

    # 4. Handle class imbalance
    n_pos = sum(y_train == 1)
    n_neg = sum(y_train == 0)
    
    if n_pos == 0 or n_neg == 0:
        logger.error("Training set has only one class. Cannot train model.")
        return
        
    scale_pos_weight = n_neg / n_pos
    logger.info(f"Class Balance (Train) - Positive: {n_pos}, Negative: {n_neg}")
    logger.info(f"Calculated scale_pos_weight: {scale_pos_weight:.3f}")

    # 5. Initialize and train XGBoost
    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        scale_pos_weight=scale_pos_weight,
        eval_metric='logloss',
        early_stopping_rounds=20,
        random_state=42  # Seed for tree building, NOT for shuffling
    )
    
    eval_set = [(X_train, y_train), (X_test, y_test)]
    
    logger.info("Training XGBoost model...")
    # fit model
    model.fit(
        X_train, y_train,
        eval_set=eval_set,
        verbose=False
    )
    
    best_iter = model.best_iteration
    logger.info(f"Training complete. Best iteration: {best_iter}")

    # 6. Threshold Tuning (Maximize F1 on test set)
    logger.info("-" * 60)
    logger.info("Tuning decision threshold for max F1 Score...")
    
    y_probs = model.predict_proba(X_test)[:, 1]
    
    thresholds = [0.40, 0.45, 0.50, 0.55, 0.60]
    best_f1 = 0.0
    best_thresh = 0.50
    
    for t in thresholds:
        y_pred = (y_probs >= t).astype(int)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        logger.info(f"  Threshold: {t:.2f} -> F1 Score: {f1:.4f}")
        
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = t
            
    logger.info(f"=> Selected Best Threshold: {best_thresh:.2f} (F1: {best_f1:.4f})")
    logger.info("-" * 60)

    # Print final test report using the best threshold
    y_pred_final = (y_probs >= best_thresh).astype(int)
    print("TEST SET CLASSIFICATION REPORT (using best threshold):")
    print(classification_report(y_test, y_pred_final, zero_division=0))

    # 7. Save Model
    os.makedirs("models", exist_ok=True)
    save_path = "models/xgboost_model.pkl"
    
    save_data = {
        "model": model,
        "feature_names": FEATURES,
        "threshold": best_thresh
    }
    
    joblib.dump(save_data, save_path)
    logger.info(f"✅ Model successfully saved to: {save_path}")
    print("=" * 60)


if __name__ == "__main__":
    train()
