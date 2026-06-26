import os
import json
import yaml
import hashlib
import pandas as pd
import numpy as np
from datetime import datetime

class PatternDatabase:
    @staticmethod
    def calc_metrics(g):
        wins = g[g['result'] == 'WIN']
        losses = g[g['result'] == 'LOSS']
        timeouts = g[g['result'] == 'TIMEOUT']
        
        win_count = len(wins) + len(timeouts[timeouts['pnl_r'] > 0])
        win_rate = win_count / len(g) * 100 if len(g) > 0 else 0
        
        gross_profit = g[g['pnl_r'] > 0]['pnl_r'].sum()
        gross_loss = abs(g[g['pnl_r'] < 0]['pnl_r'].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else 99.0
        
        r_mults = g['pnl_r']
        exp_r = r_mults.mean() if not r_mults.empty else 0.0
        
        avg_win_r = r_mults[r_mults > 0].mean() if not r_mults[r_mults > 0].empty else 0.0
        avg_loss_r = r_mults[r_mults < 0].mean() if not r_mults[r_mults < 0].empty else 0.0
        median_r = r_mults.median() if not r_mults.empty else 0.0
        
        cum_pnl = r_mults.cumsum()
        peak = cum_pnl.cummax()
        dd = peak - cum_pnl
        max_dd = dd.max() if not dd.empty else 0.0
        
        max_single_trade_r = r_mults.max() if not r_mults.empty else 0.0
        total_r_profit = r_mults[r_mults > 0].sum()
        outlier_score = max_single_trade_r / total_r_profit if total_r_profit > 0 else 0.0

        return pd.Series({
            'Trades': len(g),
            'PF': pf,
            'Exp_R': exp_r,
            'WinRate': win_rate,
            'AvgWin_R': avg_win_r,
            'AvgLoss_R': avg_loss_r,
            'Median_R': median_r,
            'MaxDD': max_dd,
            'Outlier_Dep': outlier_score,
            'UniqueFeatures': g['feature_uuid'].nunique() if 'feature_uuid' in g.columns else 0
        })

    @staticmethod
    def calc_stability(df_group):
        if len(df_group) < 10:
            return [0.0]*5
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
    def generate_pattern_id(feature_signature):
        sig_str = json.dumps(feature_signature, sort_keys=True)
        pattern_hash = hashlib.md5(sig_str.encode('utf-8')).hexdigest()
        return pattern_hash, f"PD_{pattern_hash[:16]}"

    @staticmethod
    def mine_patterns(df_merged, base_dir, sl_atr_mult, tp_atr_mult, output_suffix=""):
        core_cols = ['symbol', 'session_label', 'regime', 'direction', 'atr_bucket', 'adx_bucket', 'trend_bucket', 'horizon']
        grouped = df_merged.groupby(core_cols, observed=False)
        
        router_rules = {}
        all_patterns_db = []
        discovered_json = []
        blacklist_json = []
        
        for name, group in grouped:
            if group.empty: continue
            
            sym, sess, reg, dir_cand, atr_b, adx_b, trend_b, horizon = name
            
            metrics = PatternDatabase.calc_metrics(group)
            trades = metrics['Trades']
            pf = metrics['PF']
            expr = metrics['Exp_R']
            outlier = metrics['Outlier_Dep']
            unique_features = metrics['UniqueFeatures']
            
            pfs = PatternDatabase.calc_stability(group)
            verdict = PatternDatabase.get_stability_verdict(pfs, trades)
            
            feature_signature = {
                "symbol": sym,
                "session_label": sess,
                "regime": reg,
                "direction": dir_cand,
                "horizon": int(horizon),
                "atr_bucket": atr_b,
                "adx_bucket": adx_b,
                "trend_bucket": trend_b
            }
            
            p_hash, p_id = PatternDatabase.generate_pattern_id(feature_signature)
            
            promo_status = "REJECTED"
            if trades >= 50:
                if pf >= 1.20 and expr > 0 and outlier <= 0.35 and verdict in ["STABLE", "HIGH_VARIANCE", "ACCEPTABLE"]:
                    promo_status = "RESEARCH_VALIDATED" if trades >= 100 else "RESEARCH_DISCOVERED"
            
            record = {
                "pattern_id": p_id,
                "pattern_hash": p_hash,
                "feature_signature": json.dumps(feature_signature),
                "symbol": sym,
                "session_label": sess,
                "regime": reg,
                "direction": dir_cand,
                "horizon": int(horizon),
                "source_feature_count": int(unique_features),
                "source_outcome_count": int(trades),
                "occurrences": int(trades),
                "win_rate": float(metrics['WinRate']),
                "profit_factor": float(pf),
                "expectancy_r": float(expr),
                "avg_win_r": float(metrics['AvgWin_R']),
                "avg_loss_r": float(metrics['AvgLoss_R']),
                "median_r": float(metrics['Median_R']),
                "max_dd": float(metrics['MaxDD']),
                "outlier_dependency_score": float(outlier),
                "stability_verdict": verdict,
                "confidence_score": float(min(0.99, round(1 - outlier, 2))),
                "promotion_status": promo_status,
                "created_at": datetime.now().isoformat()
            }
            all_patterns_db.append(record)
            
            legacy_record = record.copy()
            legacy_record['pfs_progression'] = [round(p, 2) for p in pfs]
            
            if promo_status == "REJECTED":
                if trades >= 50:
                    blacklist_json.append(legacy_record)
                continue
                
            discovered_json.append(legacy_record)
            
            if sym not in router_rules: router_rules[sym] = {}
            if sess not in router_rules[sym]: router_rules[sym][sess] = {}
            
            rule_key = f"{dir_cand}_{reg}"
            rule_entry = {
                "rule_id": p_id,
                "source_pattern_id": p_id,
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
                "source_feature_count": int(unique_features),
                "source_outcome_count": int(trades),
                "confidence_score": float(min(0.99, round(1 - outlier, 2))),
                "stability_verdict": verdict,
                "promotion_status": promo_status,
                "shadow_passed": False,
                "live_passed": False,
                "source_report": "PATTERN_DISCOVERY_REPORT",
                "generated_at": datetime.now().isoformat()
            }
            
            if rule_key not in router_rules[sym][sess]:
                router_rules[sym][sess][rule_key] = rule_entry
            else:
                if pf > router_rules[sym][sess][rule_key]['historical_pf']:
                    router_rules[sym][sess][rule_key] = rule_entry

        final_yaml_rules = {}
        for sym, sess_dict in router_rules.items():
            final_yaml_rules[sym] = {}
            for sess, keys_dict in sess_dict.items():
                final_yaml_rules[sym][sess] = list(keys_dict.values())

        # Save Parquet Database
        store_path = os.path.join(base_dir, 'data', 'pattern_store')
        os.makedirs(store_path, exist_ok=True)
        if all_patterns_db:
            df_patterns = pd.DataFrame(all_patterns_db).drop_duplicates(subset=['pattern_hash'])
            db_name = f'pattern_database_{output_suffix}.parquet' if output_suffix else 'pattern_database.parquet'
            db_path = os.path.join(store_path, db_name)
            if os.path.exists(db_path):
                existing_df = pd.read_parquet(db_path)
                combined = pd.concat([existing_df, df_patterns]).drop_duplicates(subset=['pattern_hash'])
                combined.to_parquet(db_path, index=False)
            else:
                df_patterns.to_parquet(db_path, index=False)

        # Save JSON files
        k_dir = os.path.join(base_dir, "knowledge")
        os.makedirs(k_dir, exist_ok=True)
        disc_name = f"discovered_patterns_{output_suffix}.json" if output_suffix else "discovered_patterns.json"
        blk_name = f"pattern_blacklist_{output_suffix}.json" if output_suffix else "pattern_blacklist.json"
        with open(os.path.join(k_dir, disc_name), "w") as f: json.dump(discovered_json, f, indent=2)
        with open(os.path.join(k_dir, blk_name), "w") as f: json.dump(blacklist_json, f, indent=2)
        
        # Universal Pattern Summary
        summary = {
            "total_patterns_mined": len(all_patterns_db),
            "total_promoted": len(discovered_json),
            "total_blacklisted": len(blacklist_json),
            "generated_at": datetime.now().isoformat()
        }
        with open(os.path.join(k_dir, "universal_pattern_summary.json"), "w") as f: json.dump(summary, f, indent=2)
        
        r_dir = os.path.join(base_dir, "generated_rules")
        os.makedirs(r_dir, exist_ok=True)
        yaml_name = f"pattern_router_rules_{output_suffix}.yaml" if output_suffix else "pattern_router_rules.yaml"
        with open(os.path.join(r_dir, yaml_name), "w") as f: yaml.dump(final_yaml_rules, f, sort_keys=False)
        
        return discovered_json, blacklist_json, final_yaml_rules, len(all_patterns_db)
