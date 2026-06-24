import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DailyReport:
    def __init__(self, logs_dir="logs"):
        self.logs_dir = logs_dir
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir, exist_ok=True)
            
        self.current_date = datetime.utcnow().strftime("%Y-%m-%d")
        self.state_file = os.path.join(self.logs_dir, f"state_{self.current_date}.json")
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading daily state: {e}")
                
        return {
            "total_signals": 0,
            "approved_by_gemini": 0,
            "rejected_by_gemini": 0,
            "blocked_by_safety": 0,
            "blocked_by_news": 0,
            "blocked_by_duplicate": 0,
            "confidence_sum": 0,
            "intended_buy": 0,
            "intended_sell": 0,
            "lot_size_sum": 0.0,
            "risk_exposure_sum": 0.0
        }

    def _save_state(self):
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f)
        except Exception as e:
            logger.error(f"Error saving daily state: {e}")

    def _check_rollover(self):
        new_date = datetime.utcnow().strftime("%Y-%m-%d")
        if new_date != self.current_date:
            # Day changed, generate report for the old day
            self.generate_report()
            # Reset state for new day
            self.current_date = new_date
            self.state_file = os.path.join(self.logs_dir, f"state_{self.current_date}.json")
            self.state = self._load_state()

    def log_signal(self):
        self._check_rollover()
        self.state["total_signals"] += 1
        self._save_state()

    def log_gemini_decision(self, approved: bool, confidence: int):
        self._check_rollover()
        if approved:
            self.state["approved_by_gemini"] += 1
        else:
            self.state["rejected_by_gemini"] += 1
        self.state["confidence_sum"] += confidence
        self._save_state()

    def log_block(self, reason: str):
        self._check_rollover()
        if reason == "safety":
            self.state["blocked_by_safety"] += 1
        elif reason == "news":
            self.state["blocked_by_news"] += 1
        elif reason == "duplicate":
            self.state["blocked_by_duplicate"] += 1
        self._save_state()

    def log_intended_execution(self, direction: str, volume: float, risk_amount: float):
        self._check_rollover()
        if direction == "BUY":
            self.state["intended_buy"] += 1
        elif direction == "SELL":
            self.state["intended_sell"] += 1
            
        self.state["lot_size_sum"] += volume
        self.state["risk_exposure_sum"] += risk_amount
        self._save_state()

    def generate_report(self):
        report_file = os.path.join(self.logs_dir, f"daily_report_{self.current_date}.txt")
        total_ai_decisions = self.state["approved_by_gemini"] + self.state["rejected_by_gemini"]
        avg_confidence = self.state["confidence_sum"] / total_ai_decisions if total_ai_decisions > 0 else 0
        total_executions = self.state["intended_buy"] + self.state["intended_sell"]
        avg_lot = self.state["lot_size_sum"] / total_executions if total_executions > 0 else 0

        report_content = f"--- GoldBot Daily Dry-Run Report for {self.current_date} ---\n"
        report_content += f"Total Signals Generated: {self.state['total_signals']}\n"
        report_content += f"Approved by Gemini:      {self.state['approved_by_gemini']}\n"
        report_content += f"Rejected by Gemini:      {self.state['rejected_by_gemini']}\n"
        report_content += f"Blocked by Safety:       {self.state['blocked_by_safety']}\n"
        report_content += f"Blocked by News:         {self.state['blocked_by_news']}\n"
        report_content += f"Blocked by Duplicate:    {self.state['blocked_by_duplicate']}\n"
        report_content += f"Average AI Confidence:   {avg_confidence:.2f}%\n"
        report_content += f"Intended BUY Count:      {self.state['intended_buy']}\n"
        report_content += f"Intended SELL Count:     {self.state['intended_sell']}\n"
        report_content += f"Average Intended Lot:    {avg_lot:.2f}\n"
        report_content += f"Estimated Risk Exposure: ${self.state['risk_exposure_sum']:.2f}\n"
        report_content += "--------------------------------------------------\n"

        try:
            with open(report_file, "w") as f:
                f.write(report_content)
            logger.info(f"Daily report generated: {report_file}")
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")

daily_report = DailyReport()
