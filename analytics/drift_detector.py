import logging

logger = logging.getLogger("GoldBot.DriftDetector")

class DriftDetector:
    @staticmethod
    def check_drift(features_dict, metadata, z_threshold=3.0, max_outliers=2):
        drift_stats = metadata.get("drift_stats", {})
        if not drift_stats:
            return False, "No drift stats in metadata"
            
        outliers = []
        drift_data = {}
        for feature, val in features_dict.items():
            if feature in drift_stats:
                mean = drift_stats[feature]["mean"]
                std = drift_stats[feature]["std"]
                
                if std > 0:
                    z_score = abs(val - mean) / std
                    drift_data[feature] = z_score
                    if z_score > z_threshold:
                        outliers.append(f"{feature} (z={z_score:.2f})")
                        
        is_drifted = len(outliers) > max_outliers
        
        # Save for dashboard
        try:
            import json, os
            os.makedirs("reports", exist_ok=True)
            with open("reports/latest_drift.json", "w") as f:
                json.dump({"timestamp": __import__('datetime').datetime.utcnow().isoformat(), "drifts": drift_data}, f, indent=4)
        except Exception:
            pass
        
        if is_drifted:
            reason = f"HIGH DRIFT: {len(outliers)} outliers detected > {z_threshold} SD. {outliers}"
            logger.warning(reason)
            return True, reason
            
        if outliers:
            reason = f"Minor Drift: {len(outliers)} outliers detected. {outliers}"
            logger.info(reason)
            return False, reason
            
        return False, "No significant drift"

drift_detector = DriftDetector()
