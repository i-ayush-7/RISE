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
    data_mode: str
    is_simulated: property

    @property
    def is_simulated(self):
        return self.data_mode != "live"
        
    @is_simulated.setter
    def is_simulated(self, value):
        pass

    @abstractmethod
    def get_alerts(self) -> List[Alert]:
        pass

class FixtureAlertProvider(AlertProvider):
    def __init__(self, scenario: str, fixtures_dir: Optional[Path] = None):
        self.name = "fixture"
        self.data_mode = "simulated"
        self.scenario = scenario
        self.fixtures_dir = fixtures_dir if fixtures_dir is not None else Path(__file__).parent.parent / "fixtures"

    def get_alerts(self) -> List[Alert]:
        import datetime
        self.retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        filepath = self.fixtures_dir / f"alerts_{self.scenario}.json"
        if not filepath.exists():
            raise ValueError(f"Fixture file not found: {filepath.name}")
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except UnicodeDecodeError:
            raise ValueError("Fixture file is invalid: not valid UTF-8 text")
        except json.JSONDecodeError:
            raise ValueError("Fixture file is invalid: invalid JSON")
            
        if not isinstance(data, list):
            raise ValueError("Fixture file is invalid: not a list")
            
        valid_fields = {'id', 'hazard', 'severity', 'headline', 'area_description', 'issued_at', 'source', 'instructions', 'expires_at'}
        required_fields = {'id', 'hazard', 'severity', 'headline', 'area_description', 'issued_at', 'source'}
            
        alerts = []
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Fixture file is invalid: item is not an object")
                
            for req in required_fields:
                if req not in item:
                    raise ValueError(f"Fixture file is invalid: missing field {req}")
                    
            for key in item.keys():
                if key not in valid_fields:
                    raise ValueError(f"Fixture file is invalid: unknown field {key}")
                    
            for key, val in item.items():
                if key in ('instructions', 'expires_at'):
                    if val is not None and not isinstance(val, str):
                        raise ValueError(f"Fixture file is invalid: {key} must be text")
                else:
                    if not isinstance(val, str) or val == "":
                        raise ValueError(f"Fixture file is invalid: {key} must be text")
                    
            alerts.append(Alert(**item))
        return alerts

def get_provider() -> AlertProvider:
    source = os.environ.get("RISE_ALERT_SOURCE", "fixture")
    if source == "fixture":
        scenario = os.environ.get("RISE_FIXTURE_SCENARIO", "flood_warning")
        if not re.match(r'^[a-z0-9_]+$', scenario):
            raise ValueError("Invalid scenario name. Only lowercase letters, digits, and underscores allowed.")
        return FixtureAlertProvider(scenario)
    elif source == "nws":
        point = os.environ.get("RISE_NWS_POINT", "")
        import rise.nws
        return rise.nws.NWSAlertProvider(point)
    elif source == "nws_recorded":
        recording = os.environ.get("RISE_NWS_RECORDING", "sample")
        import rise.nws
        return rise.nws.RecordedAlertProvider(recording)
    else:
        raise ValueError(f"Unknown alert source: {source}. Valid options: fixture, nws, nws_recorded")
