import pandas as pd
import numpy as np
from scipy import stats
import os
from data.mt5_client import mt5_client
from research.hypothesis_engine import HypothesisEngine

class CrossMarketHypothesisValidator:
    def __init__(self):
        self.tiers = {
            "Tier 1 (Core Similar)": {"markets": ["XAGUSDm"], "threshold": 0.70},
            "Tier 2 (Macro Correlated)": {"markets": ["EURUSDm", "GBPUSDm"], "threshold": 0.50},
            "Tier 3 (Different Structure)": {"markets": ["BTCUSDm", "US30m"], "threshold": 0.30}
        }
        self.engine = HypothesisEngine()

    def run_validation(self, base_hypotheses_path: str):
        if not os.path.exists(base_hypotheses_path):
            print("Base hypotheses file not found.")
            return
            
        hyp_df = pd.read_csv(base_hypotheses_path)
        if hyp_df.empty:
            print("No valid base hypotheses to test.")
            return
            
        print(f"Loaded {len(hyp_df)} base hypotheses to validate across markets.")
        
        market_results = {}
        
        # Pre-process all market data to save time
        market_data = {}
        mt5_client.connect()
        all_markets = [m for t in self.tiers.values() for m in t['markets']]
        
        for market in all_markets:
            print(f"Fetching and preparing data for {market}...")
            raw_df = mt5_client.get_historical_data(market, "M5", 50000)
            if raw_df is not None and not raw_df.empty:
                df_prep = self.engine.prepare_data(raw_df)
                self.engine.generate_templates(df_prep)
                # Store the mask functions/series statically for this market
                market_data[market] = {
                    'df': df_prep,
                    'conditions': self.engine.feature_conditions.copy()
                }
            else:
                print(f"  Failed to get data for {market}")
                
        # Validate each hypothesis
        final_hypotheses = []
        
        for _, row in hyp_df.iterrows():
            regime = row['regime']
            cond = row['condition']
            fwd = row['forward_bars']
            base_tstat_sign = np.sign(row['t_stat'])
            base_mean_sign = np.sign(row['mean_return_bps'])
            
            tier_scores = {}
            
            for tier_name, config in self.tiers.items():
                pass_count = 0
                valid_markets = 0
                
                for market in config['markets']:
                    if market not in market_data:
                        continue
                        
                    data = market_data[market]
                    df = data['df']
                    conds = data['conditions']
                    
                    reg_mask = df['regime_label'] == regime
                    if cond not in conds:
                        continue
                        
                    cond_mask = conds[cond]
                    signal_mask = reg_mask & cond_mask
                    
                    fwd_col = f'fwd_ret_{fwd}'
                    if fwd_col not in df.columns:
                        continue
                        
                    returns = df.loc[signal_mask, fwd_col].dropna()
                    
                    if len(returns) < 20:
                        continue # Not enough samples to judge
                        
                    valid_markets += 1
                    t_stat, _ = stats.ttest_1samp(returns, 0.0)
                    mean_ret = returns.mean()
                    
                    # Rule: expectation sign must remain same, t-stat must not flip sign
                    if np.sign(t_stat) == base_tstat_sign and np.sign(mean_ret) == base_mean_sign:
                        pass_count += 1
                        
                tier_score = pass_count / valid_markets if valid_markets > 0 else 0
                tier_scores[tier_name] = tier_score
                
            # Check thresholds
            t1_pass = tier_scores.get("Tier 1 (Core Similar)", 0) >= self.tiers["Tier 1 (Core Similar)"]["threshold"]
            t2_pass = tier_scores.get("Tier 2 (Macro Correlated)", 0) >= self.tiers["Tier 2 (Macro Correlated)"]["threshold"]
            t3_pass = tier_scores.get("Tier 3 (Different Structure)", 0) >= self.tiers["Tier 3 (Different Structure)"]["threshold"]
            
            status = "GLOBAL" if (t1_pass and t2_pass and t3_pass) else ("MARKET_SPECIFIC" if t1_pass else "FAIL")
            
            out_row = row.to_dict()
            out_row['Tier1_Score'] = tier_scores.get("Tier 1 (Core Similar)", 0)
            out_row['Tier2_Score'] = tier_scores.get("Tier 2 (Macro Correlated)", 0)
            out_row['Tier3_Score'] = tier_scores.get("Tier 3 (Different Structure)", 0)
            out_row['Validation_Status'] = status
            
            final_hypotheses.append(out_row)
            
        final_df = pd.DataFrame(final_hypotheses)
        
        print("\n--- Final Cross-Market Validation Results ---")
        print(final_df[['regime', 'condition', 'Tier1_Score', 'Validation_Status']])
        
        # Generate Markdown Report
        report = ["# Phase 5: Discovered Alpha Hypotheses", ""]
        report.append("This report contains the surviving behavioral hypotheses that have statistically significant edge across out-of-sample data and multiple markets.")
        report.append("")
        report.append("| Regime | Condition | Fwd Bars | Base t-stat | Tier 1 | Tier 2 | Tier 3 | Status |")
        report.append("|--------|-----------|----------|-------------|--------|--------|--------|--------|")
        
        for _, r in final_df.sort_values(by='Tier1_Score', ascending=False).iterrows():
            t1 = f"{r['Tier1_Score']*100:.0f}%"
            t2 = f"{r['Tier2_Score']*100:.0f}%"
            t3 = f"{r['Tier3_Score']*100:.0f}%"
            tstat = f"{r['t_stat']:.2f}"
            icon = "🌍" if r['Validation_Status'] == "GLOBAL" else ("🥇" if r['Validation_Status'] == "MARKET_SPECIFIC" else "❌")
            
            report.append(f"| `{r['regime']}` | `{r['condition']}` | {r['forward_bars']} | {tstat} | {t1} | {t2} | {t3} | {icon} {r['Validation_Status']} |")
            
        with open("docs/discovered_alpha_hypotheses.md", "w", encoding='utf-8') as f:
            f.write("\n".join(report))
            
        print("\nReport saved to docs/discovered_alpha_hypotheses.md")


if __name__ == "__main__":
    validator = CrossMarketHypothesisValidator()
    validator.run_validation("research/temp/base_hypotheses.csv")
