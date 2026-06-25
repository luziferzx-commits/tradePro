import os
import pandas as pd
from datetime import datetime
from research.query_engine import QueryEngine
from analysis.coverage_engine import CoverageEngine

class KnowledgeGraph:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.qe = QueryEngine(os.path.join(base_dir, 'data', 'pattern_store', 'pattern_database.parquet'))
        self.coverage_engine = CoverageEngine(self.qe)

    def generate_coverage_report(self):
        df_coverage = self.coverage_engine.analyze_coverage()
        if df_coverage.empty:
            return "No database found."
            
        summary = self.coverage_engine.get_summary()
        
        report = f"""# Knowledge Coverage & Blind Spot Report
*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Overall Database Coverage
- **Total Cells**: {summary.get('Total Cells', 0)}
- **RESEARCH_READY (N >= 50)**: {summary.get('RESEARCH_READY', 0)}
- **VALIDATED (High Edge)**: {summary.get('VALIDATED', 0)}
- **BLACKLISTED (Low Edge)**: {summary.get('BLACKLISTED', 0)}
- **BLIND_SPOTS (N < 50)**: {summary.get('BLIND_SPOT', 0)}

## Top 10 Critical Blind Spots (Needs More Data)
"""
        blind_spots = df_coverage[df_coverage['status'] == 'BLIND_SPOT']
        if not blind_spots.empty:
            report += blind_spots[['symbol', 'session_label', 'regime', 'direction', 'atr_bucket', 'occurrences']].sort_values('occurrences', ascending=True).head(10).to_markdown()
        else:
            report += "None"
            
        report_path = os.path.join(self.base_dir, "reports", "KNOWLEDGE_COVERAGE_REPORT.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w') as f:
            f.write(report)
            
        # JSON generation
        json_path = os.path.join(self.base_dir, "knowledge", "knowledge_graph.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        df_coverage.to_json(json_path, orient='records')
            
        return report_path
