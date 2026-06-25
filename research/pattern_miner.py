import os
import json
import yaml
import pandas as pd
import numpy as np
from datetime import datetime

class PatternMiner:
    @staticmethod
    def calc_metrics(g):
        wins = g[g['result'] == 'WIN']
        losses = g[g['result'] == 'LOSS']
        # TIMEOUTs contribute to trades and expectancy, but not explicitly to WIN/LOSS ratio unless pnl_r > 0
        timeouts = g[g['result'] == 'TIMEOUT']
        
        # Win rate: standard definition might be just WINs, but for EV calculation we use pnl_r directly.
        # Let's count wins as explicit WINs or TIMEOUTs with pnl_r > 0
        win_count = len(wins) + len(timeouts[timeouts['pnl_r'] > 0])
        win_rate = win_count / len(g) * 100 if len(g) > 0 else 0
        
        # Profit factor
        gross_profit = g[g['pnl_r'] > 0]['pnl_r'].sum()
        gross_loss = abs(g[g['pnl_r'] < 0]['pnl_r'].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else 99.0
        
        # Expectancy
        r_mults = g['pnl_r']
        exp_r = r_mults.mean() if not r_mults.empty else 0.0
        
        # Drawdown using cumulative PnL_R
        cum_pnl = r_mults.cumsum()
        peak = cum_pnl.cummax()
        dd = peak - cum_pnl
        max_dd = dd.max() if not dd.empty else 0.0
        
        # Outlier
        max_single_trade_r = r_mults.max() if not r_mults.empty else 0.0
        total_r_profit = r_mults[r_mults > 0].sum()
        outlier_score = max_single_trade_r / total_r_profit if total_r_profit > 0 else 0.0

        return pd.Series({
            'Trades': len(g),
            'PF': pf,
            'Exp_R': exp_r,
            'WinRate': win_rate,
            'MaxDD': max_dd,
            'Outlier_Dep': outlier_score
        })

    @staticmethod
    def calc_stability(df_group):
        if len(df_group) < 10:
            return [0.0]*5
        
        # Sort by entry time
        df_sorted = df_group.sort_index()
        chunk_size = max(1, len(df_sorted) // 5)
        
        pfs = []
        for i in range(1, 6):
            end_idx = min(i * chunk_size, len(df_sorted))
            if i == 5: end_idx = len(df_sorted)
            chunk = df_sorted.iloc[:end_idx]
            g_profit = chunk[chunk['pnl_r'] > 0]['pnl_r'].sum()
            g_loss = abs(chunk[chunk['pnl_r'] < 0]['pnl_r'].sum())
            pfs.append(g_profit / g_loss if g_loss > 0 else 99.0)
        return pfs

    @staticmethod
    def get_stability_verdict(pfs, trades):
        if trades < 50: return "INSUFFICIENT_SAMPLE"
        final_pf = pfs[-1]
        if final_pf < 1.0: return "UNSTABLE"
        
        max_pf = max(pfs)
        if max_pf > 1.5 and final_pf < 1.1: return "DECAYING"
        
        valid_pfs = [p for p in pfs if p < 50.0]
        if len(valid_pfs) > 1 and np.std(valid_pfs) > 1.0:
            return "HIGH_VARIANCE"
            
        return "STABLE"

    @staticmethod
    def mine_patterns(df_merged, base_dir, sl_atr_mult, tp_atr_mult):
        # df_merged contains features + outcomes
        # We group by the core dimensions + horizon
        core_cols = ['symbol', 'session_label', 'regime', 'direction', 'atr_bucket', 'adx_bucket', 'trend_bucket', 'horizon']
        
        grouped = df_merged.groupby(core_cols, observed=False)
        
        router_rules = {}
        discovered_json = []
        blacklist_json = []
        
        for name, group in grouped:
            if group.empty: continue
            
            sym, sess, reg, dir_cand, atr_b, adx_b, trend_b, horizon = name
            
            metrics = PatternMiner.calc_metrics(group)
            trades = metrics['Trades']
            pf = metrics['PF']
            expr = metrics['Exp_R']
            outlier = metrics['Outlier_Dep']
            
            pfs = PatternMiner.calc_stability(group)
            verdict = PatternMiner.get_stability_verdict(pfs, trades)
            
            record = {
                "symbol": sym,
                "session": sess,
                "regime": reg,
                "direction": dir_cand,
                "atr_bucket": atr_b,
                "adx_bucket": adx_b,
                "trend_bucket": trend_b,
                "horizon": int(horizon),
                "trades": float(trades),
                "pf": float(pf),
                "exp_r": float(expr),
                "outlier_dep": float(outlier),
                "verdict": verdict,
                "pfs_progression": [round(p, 2) for p in pfs]
            }
            
            # Rejections
            if trades < 50:
                continue
                
            if pf < 1.20 or expr <= 0 or outlier > 0.35 or verdict not in ["STABLE", "HIGH_VARIANCE"]:
                blacklist_json.append(record)
                continue
                
            # Promotions
            promo_status = "RESEARCH_VALIDATED" if trades >= 100 else "RESEARCH_DISCOVERED"
            record['promotion_status'] = promo_status
            discovered_json.append(record)
            
            if sym not in router_rules:
                router_rules[sym] = {}
            if sess not in router_rules[sym]:
                router_rules[sym][sess] = {}
            
            rule_key = f"{dir_cand}_{reg}"
            
            rule_entry = {
                "rule_id": f"PD_{sym}_{sess}_{dir_cand}_{reg}_{horizon}",
                "version": "1.0",
                "symbol": sym,
                "session_label": sess,
                "regime": reg,
                "direction": dir_cand,
                "required_feature_buckets": {
                    "atr_bucket": atr_b,
                    "adx_bucket": adx_b,
                    "trend_bucket": trend_b
                },
                "execution_model": {
                    "horizon": int(horizon),
                    "sl_atr_mult": float(sl_atr_mult),
                    "tp_atr_mult": float(tp_atr_mult)
                },
                "historical_pf": float(pf),
                "expectancy_r": float(expr),
                "win_rate": float(metrics['WinRate']),
                "occurrences": int(trades),
                "confidence_score": float(min(0.99, round(1 - outlier, 2))),
                "stability_verdict": verdict,
                "promotion_status": promo_status,
                "shadow_passed": False,
                "live_passed": False,
                "source_report": "PATTERN_DISCOVERY_REPORT",
                "generated_at": datetime.now().isoformat()
            }
            
            # Select best horizon if multiple exist for the exact same core combo
            if rule_key not in router_rules[sym][sess]:
                router_rules[sym][sess][rule_key] = rule_entry
            else:
                # Compare PF
                if pf > router_rules[sym][sess][rule_key]['historical_pf']:
                    router_rules[sym][sess][rule_key] = rule_entry

        # Flatten rules for YAML
        final_yaml_rules = {}
        for sym, sess_dict in router_rules.items():
            final_yaml_rules[sym] = {}
            for sess, keys_dict in sess_dict.items():
                final_yaml_rules[sym][sess] = list(keys_dict.values())

        # Save JSON files
        k_dir = os.path.join(base_dir, "knowledge")
        os.makedirs(k_dir, exist_ok=True)
        with open(os.path.join(k_dir, "discovered_patterns.json"), "w") as f: json.dump(discovered_json, f, indent=2)
        with open(os.path.join(k_dir, "pattern_blacklist.json"), "w") as f: json.dump(blacklist_json, f, indent=2)
        
        r_dir = os.path.join(base_dir, "generated_rules")
        os.makedirs(r_dir, exist_ok=True)
        with open(os.path.join(r_dir, "pattern_router_rules.yaml"), "w") as f: yaml.dump(final_yaml_rules, f, sort_keys=False)
        
        return discovered_json, blacklist_json, final_yaml_rules
