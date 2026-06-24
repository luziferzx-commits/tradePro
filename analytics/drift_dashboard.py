import json
import os

class DriftDashboard:
    def __init__(self):
        self.drift_file = "reports/latest_drift.json"
        
    def generate_report(self):
        if not os.path.exists(self.drift_file):
            print("No drift data available. Wait for a prediction to occur.")
            return
            
        with open(self.drift_file, "r") as f:
            data = json.load(f)
            
        timestamp = data.get("timestamp", "Unknown")
        drifts = data.get("drifts", {})
        
        report_str = f"# Feature Drift Dashboard\n**Last Updated:** {timestamp}\n\n"
        report_str += "| Feature | Z-Score (σ) | Status |\n"
        report_str += "|---------|-------------|--------|\n"
        
        for feature, z in sorted(drifts.items(), key=lambda x: x[1], reverse=True):
            if z > 3.0:
                status = "🚨 HIGH DRIFT"
            elif z > 2.0:
                status = "⚠️ Warning"
            else:
                status = "✅ Normal"
            report_str += f"| {feature} | {z:.2f}σ | {status} |\n"
            
        report_path = "reports/drift_dashboard.md"
        os.makedirs("reports", exist_ok=True)
        with open(report_path, "w", encoding='utf-8') as f:
            f.write(report_str)
            
        print(f"Drift Dashboard generated: {report_path}")

dashboard = DriftDashboard()

if __name__ == "__main__":
    dashboard.generate_report()
