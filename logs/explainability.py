import os
import csv
import logging
from datetime import datetime
from logs.telemetry import telemetry_db

logger = logging.getLogger("GoldBot.Explainability")

class ExplainabilityLogger:
    def __init__(self, output_file="results/explanations.csv"):
        self.output_file = output_file
        self.fieldnames = [
            "timestamp", "symbol", "session", "regime", 
            "market_score", "ml_probability", "prod_probability", "candidate_probability",
            "probability_gap_abs", "probability_gap_signed",
            "session_health", "risk_multiplier", "health_dynamic", "health_source", "health_note",
            "decision", "decision_stage", "reasons"
        ]
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        if not os.path.exists(self.output_file):
            with open(self.output_file, mode='w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()

    def log_signal(self, 
                   symbol: str, 
                   session: str = "UNKNOWN", 
                   regime: str = "UNKNOWN",
                   market_score: float = 0.0, 
                   ml_probability: float = 0.0,
                   prod_probability: float = 0.0,
                   candidate_probability: float = 0.0,
                   probability_gap_abs: float = 0.0,
                   probability_gap_signed: float = 0.0,
                   session_health: str = "HEALTHY", 
                   risk_multiplier: float = 1.0,
                   health_dynamic: bool = False,
                   health_source: str = "initialized_default",
                   health_note: str = "PnL feedback loop not implemented in A1",
                   decision: str = "REJECT", 
                   decision_stage: str = "UNKNOWN",
                   reasons: list = None):
        
        if reasons is None:
            reasons = []
            
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        row = {
            "timestamp": timestamp,
            "symbol": symbol,
            "session": session,
            "regime": regime,
            "market_score": market_score,
            "ml_probability": ml_probability,
            "prod_probability": prod_probability,
            "candidate_probability": candidate_probability,
            "probability_gap_abs": probability_gap_abs,
            "probability_gap_signed": probability_gap_signed,
            "session_health": session_health,
            "risk_multiplier": risk_multiplier,
            "health_dynamic": health_dynamic,
            "health_source": health_source,
            "health_note": health_note,
            "decision": decision,
            "decision_stage": decision_stage,
            "reasons": reasons
        }
        
        # Write to Telemetry Database
        telemetry_db.insert_signal(row)
        
        # Write to CSV
        try:
            csv_row = row.copy()
            csv_row["health_dynamic"] = str(health_dynamic).lower()
            csv_row["reasons"] = " | ".join(reasons) if reasons else "None"
            with open(self.output_file, mode='a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(csv_row)
        except Exception as e:
            logger.error(f"Failed to write explainability CSV log: {e}")

        # Pretty print to console
        self._pretty_print(row, reasons)

    def _pretty_print(self, row, reasons):
        print(f"\n{row['symbol']} [{row['timestamp']} UTC]")
        print(f"Session: {row['session']}")
        print(f"Regime: {row['regime']}")
        print(f"Market Score: {row['market_score']:.1f}")
        print(f"ML Prob: {row['ml_probability']:.2f} | Prod: {row['prod_probability']:.3f} | Cand: {row['candidate_probability']:.3f} | Gap: {row['probability_gap_signed']:.3f}")
        print(f"Session Health: {row['session_health']} (Dynamic: {row['health_dynamic']})")
        
        decision_color = "\033[92m" if row['decision'] == "ACCEPT" else "\033[91m"
        reset_color = "\033[0m"
        
        print(f"\nDecision: {decision_color}{row['decision']}{reset_color}")
        print(f"Stage: {row['decision_stage']}")
        print("Reasons:")
        if not reasons:
            print("- Passed all filters")
        else:
            for r in reasons:
                print(f"- {r}")
        print("-" * 40)

explainability_logger = ExplainabilityLogger()
