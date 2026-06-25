import os
import sys
import logging
import glob
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml.dataset_builder import build_dataset
from ml.predictor import MLPredictor
from scripts.backtest_all_markets import load_symbols
import pandas as pd
from xgboost import XGBClassifier

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("MLOps.AutoRetrain")

def evaluate_model(model, X_test, y_test):
    # Simplified evaluation: returns Win Rate and Expectancy for threshold 0.50
    probs = model.predict_proba(X_test)[:, 1]
    trades = probs >= 0.50
    if sum(trades) == 0:
        return 0, 0
    wins = sum(trades & (y_test == 1))
    losses = sum(trades & (y_test == 0))
    win_rate = wins / sum(trades)
    expectancy = ((wins * 2.5) - (losses * 1.0)) / sum(trades)
    return win_rate, expectancy

def auto_retrain():
    logger.info("=" * 60)
    logger.info(" AUTOMATED MLOPS RETRAINING PIPELINE ")
    logger.info("=" * 60)
    
    symbols_config = load_symbols()
    
    for symbol, cfg in symbols_config.items():
        if not cfg.get("enabled", False):
            continue
            
        logger.info(f"\n[1] Building latest dataset for {symbol}...")
        build_dataset(symbol, cfg.get("primary_timeframe", "M5"), 2.0)
        
        # Load dataset
        files = sorted(glob.glob(f"datasets/{symbol}/{symbol}_dataset_atr_*.csv"), reverse=True)
        if not files:
            logger.warning(f"Failed to generate dataset for {symbol}.")
            continue
            
        df = pd.read_csv(files[0])
        features = ["final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
                    "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc", "is_high_volatility", 
                    "is_buy", "recent_high_20_distance", "recent_low_20_distance"]
        
        df = df.dropna(subset=features + ["label"])
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]
        
        if len(train_df) < 100:
            continue
            
        X_train, y_train = train_df[features], train_df["label"]
        X_test, y_test = test_df[features], test_df["label"]
        
        logger.info(f"[2] Training Candidate Model for {symbol}...")
        candidate = XGBClassifier(n_estimators=300, learning_rate=0.01, max_depth=4, random_state=42)
        candidate.fit(X_train, y_train)
        
        cand_wr, cand_exp = evaluate_model(candidate, X_test, y_test)
        
        logger.info(f"[3] Evaluating Candidate: Win Rate={cand_wr:.1%}, Expectancy={cand_exp:.2f}R")
        
        # Load production model if exists, otherwise candidate becomes production
        prod_model_path = f"models/{symbol}/xgboost_model.pkl"
        promote = False
        
        if os.path.exists(prod_model_path):
            try:
                import joblib
                prod_model = joblib.load(prod_model_path)
                prod_wr, prod_exp = evaluate_model(prod_model, X_test, y_test)
                logger.info(f"    Production Model: Win Rate={prod_wr:.1%}, Expectancy={prod_exp:.2f}R")
                
                if cand_exp > prod_exp:
                    logger.info("    Candidate outperforms Production. Promoting!")
                    promote = True
                else:
                    logger.info("    Production is still better or equal. Discarding Candidate.")
            except Exception as e:
                logger.error(f"Error loading production model: {e}")
                promote = True
        else:
            logger.info("    No production model exists. Promoting Candidate automatically.")
            promote = True
            
        if promote:
            import joblib
            os.makedirs(f"models/{symbol}", exist_ok=True)
            joblib.dump(candidate, prod_model_path)
            logger.info(f"[4] Deployed new Production model for {symbol}.")

if __name__ == "__main__":
    auto_retrain()
