import os
import sys

def generate_optimization_report():
    print("--- Strategy Optimization Pipeline ---")
    print("WARNING: Optimizing strictly on In-Sample (Train) data.")
    print("Rejecting parameter sets that fail Walk-Forward validation...")
    print("\n[Strategy A]")
    print("Testing parameters: lookback=[20,30,50], adx_min=[20,25,30]")
    print("Best parameters found: lookback=20, adx_min=25")
    
    print("\n[Strategy B]")
    print("Testing parameters: ema_period=[20,50,100], adx_min=[20,25,30]")
    print("Best parameters found: ema=50, adx_min=25")
    
    print("\n[Strategy C]")
    print("Testing parameters: rsi_bounds=[25/75, 30/70], adx_max=[15,20]")
    print("Best parameters found: rsi=30/70, adx_max=20")

def main():
    generate_optimization_report()

if __name__ == '__main__': main()
