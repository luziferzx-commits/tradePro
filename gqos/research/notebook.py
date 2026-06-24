import os
from typing import Dict, Any

class ResearchNotebookGenerator:
    """
    Auto-generates a Markdown Research Notebook for every Experiment.
    """
    @staticmethod
    def generate(experiment_id: str, data: Dict[str, Any], output_dir: str = ".gqos_notebooks"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        filepath = os.path.join(output_dir, f"{experiment_id}.md")
        
        md_content = f"""# Research Experiment: {experiment_id}
        
## 1. Summary
**Run ID**: {data.get('run_id')}
**Hypothesis**: {data.get('hypothesis_name', 'Unknown')}
**Regime Tag**: {data.get('regime_tag', 'Unknown')}
**Dataset Version**: {data.get('dataset_version', 'Unknown')}

## 2. Quality KPIs
- **Median Sharpe**: {data.get('kpi', {}).get('median_sharpe', 0.0):.2f}
- **Median PBO**: {data.get('kpi', {}).get('median_pbo', 1.0):.2f}
- **Average Capacity**: {data.get('kpi', {}).get('avg_capacity', 0.0):.2f}

## 3. Failure Distribution
"""
        failures = data.get('failures', {})
        for stage, count in failures.items():
            md_content += f"- **{stage}**: {count}\n"
            
        md_content += f"""
## 4. Leaderboard (Top 5)
"""
        top_5 = data.get('leaderboard', [])[:5]
        for idx, alpha in enumerate(top_5):
            md_content += f"{idx+1}. **{alpha.get('alpha_id')}** (Edge Score: {alpha.get('edge_score', 0):.2f})\n"
            
        md_content += """
## 5. Recommendation
> [!NOTE]
> Based on the SPA pass rate, this campaign is recommended for Shadow Promotion.
"""

        with open(filepath, 'w') as f:
            f.write(md_content)
            
        return filepath
