import os
import json
import pandas as pd
import numpy as np
from feature_elimination import FeatureEliminator
from decay_engine import run_decay_test
from cross_market_validation import CrossMarketValidator
import warnings
warnings.filterwarnings('ignore')

def generate_kill_list_report(el_results, decay_results, cm_results):
    report = ["# Phase 4: Feature Kill List & Robustness Report", ""]
    
    report.append("## 1. 3-Layer Feature Elimination (MDA & SHAP)")
    report.append("| Feature | MDA | S-Score | SHAP Consistency | Classification |")
    report.append("|---------|-----|---------|------------------|----------------|")
    
    keep_features = []
    
    for feat, data in sorted(el_results.items(), key=lambda x: x[1]['Classification']):
        mda = f"{data['MDA']:.4f}"
        s_score = f"{data['S_Score']:.2f}"
        shap_cons = f"{data['SHAP_consistency'] * 100:.1f}%"
        cls = data['Classification']
        report.append(f"| `{feat}` | {mda} | {s_score} | {shap_cons} | **{cls}** |")
        
        if "KEEP" in cls:
            keep_features.append(feat)
            
    report.append("")
    report.append("## 2. Feature Decay Test")
    report.append("| Feature | Lag 10 Drop | Noise Flag |")
    report.append("|---------|-------------|------------|")
    
    for feat, data in decay_results.items():
        base = data['curve'][0]
        lag10 = data['curve'].get(10, 0)
        drop = (base - lag10) / base * 100 if base > 0 else 0
        is_noise = "🚨 YES" if data['is_microstructure_noise'] else "✅ NO"
        report.append(f"| `{feat}` | {drop:.1f}% | {is_noise} |")
        
    report.append("")
    report.append("## 3. Cross-Market Robustness (Core Features Only)")
    if cm_results:
        report.append("| Market | Tier | OOS PF | Status |")
        report.append("|--------|------|--------|--------|")
        tiers = {"XAUUSDm": 1, "XAGUSDm": 1, "EURUSDm": 2, "GBPUSDm": 2, "BTCUSDm": 3, "US30m": 3}
        for market, data in cm_results.items():
            tier = tiers.get(market, "Unknown")
            pf = f"{data['pf']:.2f}"
            status = data['status']
            icon = "✅" if status == "PASS" else ("⚠️" if status == "MISSING" else "❌")
            report.append(f"| `{market}` | {tier} | {pf} | {icon} {status} |")
    else:
        report.append("*Cross-Market validation skipped or failed.*")
        
    report.append("")
    report.append("## Final Surviving Features")
    report.append("The following features survived all Hedge Fund-grade tests and will be used for Phase 5:")
    if keep_features:
        for f in keep_features:
            report.append(f"- `{f}`")
    else:
        report.append("*(None. All features were killed. We must engineer new alpha.)*")
        
    with open("docs/phase4_kill_list.md", "w", encoding='utf-8') as f:
        f.write("\n".join(report))
        
    print("\nPhase 4 complete. Report saved to docs/phase4_kill_list.md")


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

if __name__ == "__main__":
    import glob
    os.environ['PYTHONPATH'] = "."
    files = glob.glob("datasets/*/*.csv")
    if not files:
        files = glob.glob("datasets/*.csv")
        
    data_file = files[-1]
    for f in files:
        if "XAUUSDm" in f:
            data_file = f
            break
            
    print(f"Starting Phase 4 execution on dataset: {data_file}")
    
    # 1. Feature Elimination
    eliminator = FeatureEliminator(data_file)
    eliminator.compute_mda_and_shap()
    el_results = eliminator.calculate_s_score()
    
    # Save partial
    os.makedirs("ml/temp", exist_ok=True)
    with open("ml/temp/feature_elimination_results.json", "w") as f:
        json.dump(el_results, f, indent=4, cls=NpEncoder)
        
    features = list(el_results.keys())
    
    # 2. Decay Engine
    decay_results = run_decay_test(data_file, features)
    
    # 3. Cross Market
    core_features = [feat for feat, data in el_results.items() if "KEEP" in data['Classification']]
    if core_features:
        validator = CrossMarketValidator(core_features)
        cm_results = validator.run_validation()
    else:
        print("\nNo features survived elimination. Skipping cross-market validation.")
        cm_results = None
        
    # 4. Report
    generate_kill_list_report(el_results, decay_results, cm_results)
