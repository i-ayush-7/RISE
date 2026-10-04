import os
import re
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from abc import ABC, abstractmethod

SEVERITY_RANK = {
    'advisory': 1,
    'watch': 2,
    'warning': 3,
    'emergency': 4
}

ALLOWED_HAZARDS = {'flood', 'storm', 'cyclone', 'heat', 'cold', 'earthquake', 'wildfire', 'other'}

@dataclass
class Alert:
    id: str
    hazard: str
    severity: str
    headline: str
    area_description: str
    issued_at: str
    source: str
    instructions: Optional[str] = None
    expires_at: Optional[str] = None

    def __post_init__(self):
        if self.hazard not in ALLOWED_HAZARDS:
            raise ValueError(f"hazard must be one of: {', '.join(sorted(ALLOWED_HAZARDS))}")
        if self.severity not in SEVERITY_RANK:
            raise ValueError(f"severity must be one of: {', '.join(sorted(SEVERITY_RANK.keys()))}")

class AlertProvider(ABC):
    name: str
    is_simulated: bool

    @abstractmethod
    def get_alerts(self) -> List[Alert]:
        pass

class FixtureAlertProvider(AlertProvider):
    def __init__(self, scenario: str):
        self.name = "fixture"
        self.is_simulated = True
        self.scenario = scenario
        self.fixtures_dir = Path(__file__).parent.parent / "fixtures"

    def get_alerts(self) -> List[Alert]:
        filepath = self.fixtures_dir / f"alerts_{self.scenario}.json"
        if not filepath.exists():
            raise ValueError(f"Fixture file not found: {filepath.name}")
            
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        alerts = []
        for item in data:
            alerts.append(Alert(**item))
        return alerts

def get_provider() -> AlertProvider:
    source = os.environ.get("RISE_ALERT_SOURCE", "fixture")
    scenario = os.environ.get("RISE_FIXTURE_SCENARIO", "flood_warning")
    
    if source != "fixture":
        raise ValueError(f"Unknown alert source: {source}. Valid values: fixture")
        
    if not re.match(r'^[a-z0-9_]+$', scenario):
        raise ValueError("Invalid scenario name. Only lowercase letters, digits, and underscores allowed.")
        
    return FixtureAlertProvider(scenario)
