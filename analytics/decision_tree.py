import logging
import os
import sys
from datetime import datetime

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

logger = logging.getLogger(__name__)

class DecisionLogger:
    def __init__(self, logs_dir="logs"):
        self.logs_dir = logs_dir
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir, exist_ok=True)
            
        self.steps = []
        self.current_date = datetime.utcnow().strftime("%Y-%m-%d")
        self.log_file = os.path.join(self.logs_dir, f"decision_tree_{self.current_date}.log")

    def reset(self):
        self.steps = []
        self.current_date = datetime.utcnow().strftime("%Y-%m-%d")
        self.log_file = os.path.join(self.logs_dir, f"decision_tree_{self.current_date}.log")

    def log_step(self, stage_name: str, passed: bool, reason: str = ""):
        self.steps.append({
            "stage": stage_name,
            "passed": passed,
            "reason": reason
        })

    def print_tree(self, timestamp_str: str = None):
        if not self.steps:
            return

        header = f"[CANDLE CLOSED] {timestamp_str}" if timestamp_str else "[CANDLE CLOSED]"
        lines = [header]
        for i, step in enumerate(self.steps):
            lines.append("        │")
            lines.append("        ▼")
            
            icon = "✔" if step["passed"] else "❌"
            lines.append(f"{step['stage']} {icon}")
            
            if not step["passed"]:
                lines.append("        │")
                lines.append("        ▼")
                lines.append("Reason:")
                lines.append(f"{step['reason']}")
                lines.append("        │")
                lines.append("        ▼")
                lines.append("Trade Cancelled")
                break
        
        # Check if the last step was passed and it was the Execution step
        if self.steps[-1]["passed"] and self.steps[-1]["stage"] == "Execution":
            lines.append("        │")
            lines.append("        ▼")
            lines.append(f"Trade Executed: {self.steps[-1]['reason']}")

        tree_output = "\n".join(lines)
        
        # Print to console
        print(f"\n{tree_output}\n")
        
        # Append to log file
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"--- Decision Tree recorded at {now} ---\n")
                f.write(tree_output)
                f.write("\n\n")
        except Exception as e:
            logger.error(f"Failed to write decision tree to log: {e}")

decision_logger = DecisionLogger()
