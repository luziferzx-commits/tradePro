import os
import sys

def run_phase5():
    print("=========================================")
    print(" PHASE 5: Market Behavior Mining System ")
    print("=========================================")
    
    # 1. Hypothesis Engine (Generation & CPCV Validation)
    print("\n--- Step 1: Hypothesis Mining (XAUUSDm) ---")
    ret = os.system(f"{sys.executable} research/hypothesis_engine.py")
    if ret != 0:
        print("Hypothesis mining failed.")
        return
        
    # 2. Cross Market Validation
    print("\n--- Step 2: Cross-Market Behavior Validation ---")
    ret = os.system(f"{sys.executable} research/hypothesis_validation.py")
    if ret != 0:
        print("Cross-market validation failed.")
        return
        
    print("\nPhase 5 Complete. See docs/discovered_alpha_hypotheses.md for details.")

if __name__ == "__main__":
    os.environ['PYTHONPATH'] = "."
    run_phase5()
