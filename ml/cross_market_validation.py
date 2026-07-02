import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score
import glob
import os
import warnings

warnings.filterwarnings('ignore')

class CrossMarketValidator:
    def __init__(self, core_features: list):
        self.features = core_features
        self.tiers = {
            "Tier 1 (Core Similar)": {"markets": ["XAUUSDm", "XAGUSDm"], "pass_rate": 0.70},
            "Tier 2 (Macro Correlated)": {"markets": ["EURUSDm", "GBPUSDm"], "pass_rate": 0.50},
            "Tier 3 (Different Structure)": {"markets": ["BTCUSDm", "US30m"], "pass_rate": 0.30}
        }
        
    def _load_market_data(self, market: str) -> pd.DataFrame:
        files = glob.glob(f"datasets/{market}/*.csv")
        if not files:
            return None
        # get latest
        files.sort()
        df = pd.read_csv(files[-1])
        # ensure features exist
        available = [f for f in self.features if f in df.columns]
        if len(available) != len(self.features):
            return None
        return df

    def run_validation(self):
        print("--- Running Cross-Market Validation ---")
        
        # 1. Train base model on XAUUSDm
        base_df = self._load_market_data("XAUUSDm")
        if base_df is None:
            print("Base market XAUUSDm dataset not found.")
            return
            
        n_samples = len(base_df)
        train_size = int(n_samples * 0.8)
        
        X_train_base = base_df.iloc[:train_size][self.features]
        y_train_base = base_df.iloc[:train_size]['label']
        
        model = xgb.XGBClassifier(
            max_depth=2, learning_rate=0.01, n_estimators=100, subsample=0.9,
            random_state=42, eval_metric='logloss', n_jobs=-1
        )
        model.fit(X_train_base, y_train_base)
        
        print(f"Base model trained on XAUUSDm (N={train_size})")
        
        results = {}
        for tier_name, config in self.tiers.items():
            print(f"\nEvaluating {tier_name} (Threshold: {config['pass_rate'] * 100:.0f}%)")
            for market in config['markets']:
                market_df = self._load_market_data(market)
                if market_df is None:
                    print(f"  {market:8} : DATA MISSING")
                    results[market] = {"pf": 0.0, "status": "MISSING"}
                    continue
                    
                # We test on the full dataset of the other market (or the recent 20% to simulate OOS)
                test_size = int(len(market_df) * 0.2)
                df_test = market_df.iloc[-test_size:]
                X_test = df_test[self.features]
                
                preds = model.predict(X_test)
                trades_mask = preds == 1
                trades_df = df_test[trades_mask]
                
                if trades_df.empty:
                    pf = 0.0
                else:
                    wins = trades_df[trades_df['result_r'] > 0]['result_r'].sum()
                    losses = abs(trades_df[trades_df['result_r'] <= 0]['result_r'].sum())
                    pf = wins / losses if losses > 0 else 1.0
                    
                survived = pf >= config['pass_rate']
                status = "PASS" if survived else "FAIL"
                print(f"  {market:8} : OOS PF = {pf:.2f} | {status}")
                results[market] = {"pf": pf, "status": status}
                
        return results

if __name__ == "__main__":
    # We load the "KEEP" features from the elimination output
    import json
    try:
        with open("ml/temp/feature_elimination_results.json", "r") as f:
            el_results = json.load(f)
            
        core_features = [feat for feat, data in el_results.items() if data['Classification'] == 'KEEP']
        if not core_features:
            print("No features survived elimination. Using fallback set.")
            core_features = ["atr", "rsi", "macd", "is_high_volatility", "is_buy"]
    except FileNotFoundError:
        core_features = ["atr", "rsi", "macd", "is_high_volatility", "is_buy"]
        
    validator = CrossMarketValidator(core_features)
    validator.run_validation()
