"""journal/portfolio_journal.py"""
import os
import csv
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PortfolioJournal:
    def __init__(self, filename: str = "results/portfolio_decisions.csv"):
        self.filename = filename
        self.headers = [
            "timestamp", "symbol", "side", "scanner_status", "portfolio_status",
            "reason", "original_risk_pct", "final_risk_pct", "estimated_lot",
            "final_score", "var_95", "cvar_95", "warnings"
        ]
        self._ensure_file()
        
    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.headers)
            except Exception as e:
                logger.error(f"Failed to initialize portfolio journal: {e}")
                
    def log_decision(self, data: dict):
        try:
            row = [
                data.get("timestamp", datetime.utcnow().isoformat()),
                data.get("symbol", ""),
                data.get("side", ""),
                data.get("scanner_status", ""),
                data.get("portfolio_status", ""),
                data.get("reason", ""),
                f"{data.get('original_risk_pct', 0.0):.6f}",
                f"{data.get('final_risk_pct', 0.0):.6f}",
                f"{data.get('estimated_lot', 0.0):.2f}",
                f"{data.get('final_score', 0.0):.2f}",
                f"{data.get('var_95', 0.0):.2f}",
                f"{data.get('cvar_95', 0.0):.2f}",
                "|".join(data.get("warnings", []))
            ]
            with open(self.filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            logger.error(f"Failed to write to portfolio journal: {e}")
