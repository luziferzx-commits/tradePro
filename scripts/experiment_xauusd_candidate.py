import os
import json
import joblib
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from ml.dataset_builder import build_dataset
from mlops.train_production import train_and_register_production
from mlops.registry import registry
from config.settings import settings

def run_experiment():
    print("--- Starting XAUUSDm Candidate Experiment ---")
    symbol = "XAUUSDm"
    
    # 1. Build new dataset with new features
    # Using 100k candles instead of 200k to save time during this experiment but still get massive data
    dataset_path = build_dataset(symbol, "M5", 2.0)
    print(f"Dataset built at: {dataset_path}")
    
    # 2. Train Candidate Model
    version = train_and_register_production(symbol, dataset_path, status="candidate")
    print(f"Candidate model trained: {version}")
    
    # 3. Load both models for comparison
    df = pd.read_csv(dataset_path)
    
    print("Loading Candidate Model...")
    cand_dir = os.path.join("models", symbol, "candidate", version)
    cand_model = joblib.load(os.path.join(cand_dir, "xgb.pkl"))
    with open(os.path.join(cand_dir, "metadata.json"), "r") as f:
        cand_meta = json.load(f)
        
    print("Loading Production Model...")
    # Production model is currently in models/production/
    prod_model, prod_meta = registry.get_production_model() # Old global one
    if not prod_model:
        # Fallback to symbol-specific if it exists
        prod_model, prod_meta = registry.get_production_model(symbol)
        
    if not prod_model:
        print("Production model not found! Cannot compare.")
        return
        
    # 4. Backtest Comparison on the dataset
    print("Running Backtest Comparison...")
    
    # Candidate features
    cand_features = cand_meta['features']
    X_cand = df[cand_features]
    y_true = df['label']
    
    cand_probs = cand_model.predict_proba(X_cand)[:, 1]
    
    # Production features
    prod_features = prod_meta['features']
    # Ensure backward compatibility if df has old features
    X_prod = df[prod_features]
    prod_probs = prod_model.predict_proba(X_prod)[:, 1]
    
    # Calculate metrics
    def calc_metrics(probs, y, threshold=0.55):
        trades = probs >= threshold
        num_trades = trades.sum()
        if num_trades == 0:
            return {"trades": 0, "win_rate": 0, "pf": 0, "avg_prob": 0, "max_dd": 0}
            
        wins = (trades & (y == 1)).sum()
        losses = (trades & (y == 0)).sum()
        win_rate = wins / num_trades if num_trades > 0 else 0
        
        # Assume RR = 2.5
        gross_profit = wins * 2.5
        gross_loss = losses * 1.0
        pf = gross_profit / gross_loss if gross_loss > 0 else gross_profit
        
        avg_prob = probs[trades].mean() if num_trades > 0 else 0
        
        # Simple Max Drawdown Simulation
        balance = 100.0
        peak = 100.0
        max_dd = 0.0
        for i in range(len(trades)):
            if trades[i]:
                if y[i] == 1:
                    balance += 2.5
                else:
                    balance -= 1.0
                if balance > peak:
                    peak = balance
                dd = (peak - balance) / peak * 100
                if dd > max_dd:
                    max_dd = dd
                    
        return {
            "trades": num_trades,
            "win_rate": win_rate * 100,
            "pf": pf,
            "avg_prob": avg_prob,
            "max_dd": max_dd
        }
        
    cand_metrics = calc_metrics(cand_probs, y_true)
    prod_metrics = calc_metrics(prod_probs, y_true)
    
    print("\n===========================================")
    print("        BACKTEST COMPARISON REPORT         ")
    print("===========================================")
    print(f"Metric\t\t\tProduction\tCandidate")
    print("-" * 50)
    print(f"Trades Count\t\t{prod_metrics['trades']}\t\t{cand_metrics['trades']}")
    print(f"Win Rate (%)\t\t{prod_metrics['win_rate']:.2f}%\t\t{cand_metrics['win_rate']:.2f}%")
    print(f"Profit Factor\t\t{prod_metrics['pf']:.2f}\t\t{cand_metrics['pf']:.2f}")
    print(f"Max Drawdown (%)\t{prod_metrics['max_dd']:.2f}%\t\t{cand_metrics['max_dd']:.2f}%")
    print(f"Avg Probability\t\t{prod_metrics['avg_prob']:.3f}\t\t{cand_metrics['avg_prob']:.3f}")
    print("===========================================")
    
    if cand_metrics['pf'] > prod_metrics['pf'] and cand_metrics['win_rate'] > prod_metrics['win_rate']:
        print("\nCONCLUSION: Candidate model shows SUPERIOR performance.")
    else:
        print("\nCONCLUSION: Candidate model DOES NOT show clear superiority.")
        
if __name__ == "__main__":
    run_experiment()
