from gqos.research.registry.models import StrategyCard

class StrategyCardGenerator:
    def generate_markdown(self, card: StrategyCard) -> str:
        """
        Translates a StrategyCard into a standardized Markdown string.
        """
        md = []
        md.append(f"# Strategy Card: {card.purpose}")
        md.append("")
        md.append("## Overview")
        md.append(f"- **Purpose**: {card.purpose}")
        md.append(f"- **Markets**: {', '.join(card.markets)}")
        md.append(f"- **Timeframe**: {card.timeframe}")
        md.append(f"- **Data Version**: {card.data_version}")
        md.append(f"- **Optimizer Version**: {card.optimizer_version}")
        md.append(f"- **Researcher**: {card.researcher}")
        md.append(f"- **Approval Status**: {card.approval_status}")
        md.append("")
        
        md.append("## Factor Exposure")
        for factor, exposure in card.factor_exposure.items():
            md.append(f"- **{factor}**: {exposure}")
        md.append("")
        
        md.append("## Walk-Forward Performance (Out-of-Sample)")
        for metric, val in card.walk_forward_metrics.items():
            md.append(f"- **{metric}**: {val}")
        md.append("")
        
        md.append("## Risk Metrics")
        for metric, val in card.risk_metrics.items():
            md.append(f"- **{metric}**: {val}")
        md.append("")
        
        md.append("## Known Failure Modes")
        for mode in card.known_failure_modes:
            md.append(f"- {mode}")
            
        return "\n".join(md)
