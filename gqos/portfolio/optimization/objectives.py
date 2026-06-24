from gqos.portfolio.optimization.interfaces import IObjectiveFunction

class MinimizeVarianceObjective(IObjectiveFunction):
    @property
    def name(self) -> str:
        return "MinimizeVarianceObjective"

class MaximizeSharpeObjective(IObjectiveFunction):
    def __init__(self, risk_free_rate: float = 0.0):
        self.risk_free_rate = risk_free_rate

    @property
    def name(self) -> str:
        return f"MaximizeSharpeObjective(rf={self.risk_free_rate})"

class EqualRiskContributionObjective(IObjectiveFunction):
    @property
    def name(self) -> str:
        return "EqualRiskContributionObjective"
