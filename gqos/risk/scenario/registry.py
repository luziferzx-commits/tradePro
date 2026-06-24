from typing import Dict, Optional
from gqos.risk.scenario.interfaces import IScenario

class ScenarioRegistry:
    def __init__(self):
        self._scenarios: Dict[str, IScenario] = {}

    def register(self, scenario: IScenario):
        # Keyed by ID and Version to ensure we can pull exact versions
        key = f"{scenario.metadata.scenario_id}_v{scenario.metadata.version}"
        self._scenarios[key] = scenario
        # Also register as latest for this ID
        self._scenarios[scenario.metadata.scenario_id] = scenario

    def get_scenario(self, scenario_id: str, version: Optional[str] = None) -> Optional[IScenario]:
        if version:
            key = f"{scenario_id}_v{version}"
            return self._scenarios.get(key)
        return self._scenarios.get(scenario_id)
