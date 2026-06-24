class CapitalReporter:
    def __init__(self):
        pass
        
    def generate_cio_tearsheet(self, performance_data: dict, risk_data: dict, capacity_data: dict, exec_data: dict) -> dict:
        """
        Generates the Institutional Metrics Dashboard for the CIO / Investment Committee.
        """
        # CIO cares about "what broke to make it"
        
        tearsheet = {
            "Performance Layer": {
                "RAROC": f"{performance_data.get('raroc', 0.0):.2f}%",
                "Sharpe Decay (30d)": f"{performance_data.get('sharpe_decay', 0.0):.2f} pts",
                "Marginal Risk Contribution": f"{performance_data.get('marginal_risk', 0.0):.2f}%"
            },
            "Risk Layer": {
                "Live Drawdown Velocity": f"{risk_data.get('dd_velocity', 0.0):.2f} USD/s",
                "Tail Risk (CVaR 99%)": f"${risk_data.get('cvar', 0.0):,.2f}",
                "Regime Stress Index": f"{risk_data.get('regime_stress', 0.0):.2f}/10"
            },
            "Capacity Layer": {
                "Capacity Utilization": f"{capacity_data.get('utilization', 0.0):.2f}%",
                "Unused Alpha Capacity": f"${capacity_data.get('unused_capacity', 0.0):,.2f}",
                "Saturation Index": "DANGER" if capacity_data.get('utilization', 0.0) > 90 else "HEALTHY"
            },
            "Execution Layer": {
                "Slippage vs Expected": f"{exec_data.get('slippage_diff', 0.0):.2f} bps",
                "Fill Efficiency Ratio": f"{exec_data.get('fill_efficiency', 0.0):.2f}%",
                "Latency Drift Index": f"{exec_data.get('latency_drift', 0.0):.2f} ms"
            }
        }
        
        return tearsheet
