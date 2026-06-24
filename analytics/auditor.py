import os
import pandas as pd
import logging

logger = logging.getLogger("GoldBot.Auditor")

class AuditAuditor:
    def __init__(self, output_dir="artifacts"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def export_csv(self, filename: str, df: pd.DataFrame):
        path = os.path.join(self.output_dir, filename)
        df.to_csv(path, index=False)
        logger.info(f"Audit: Exported {filename} to artifacts/")
        
    def check_audit_trail(self, required_files: list):
        missing = []
        for file in required_files:
            path = os.path.join(self.output_dir, file)
            if not os.path.exists(path):
                missing.append(file)
                
        if missing:
            raise FileNotFoundError(f"Audit Failed! Missing required artifacts: {missing}")
            
        logger.info("Audit Trail Verified: All required CSVs present.")
        return True

auditor = AuditAuditor()
