from typing import Dict, List, Any
from collections import defaultdict

class FailureAnalytics:
    def __init__(self):
        # Maps pipeline stage -> count of failures
        self.stage_failures: Dict[str, int] = defaultdict(int)
        # Maps specific reason -> count
        self.reason_failures: Dict[str, int] = defaultdict(int)
        self.total_generated = 0
        
    def record_generation(self):
        self.total_generated += 1
        
    def record_failure(self, stage: str, reason: str):
        """
        Stages: Generator, Constraint, PBO, SPA, HRP, Portfolio, Paper, Promotion
        """
        self.stage_failures[stage] += 1
        self.reason_failures[reason] += 1
        
    def get_report(self) -> Dict[str, Any]:
        report = {
            "Total_Generated": self.total_generated,
            "Total_Failures": sum(self.stage_failures.values()),
            "Stage_Breakdown": dict(self.stage_failures),
            "Reason_Breakdown": dict(self.reason_failures),
            "Pass_Rate": 0.0
        }
        if self.total_generated > 0:
            passed = self.total_generated - report["Total_Failures"]
            report["Pass_Rate"] = passed / self.total_generated
            
        return report
