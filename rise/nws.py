import json
import logging
import time
import urllib.request
from typing import List, Optional, Callable, Dict, Any
from urllib.error import URLError, HTTPError
from rise.alerts import Alert, AlertProvider
import hashlib
import re

logger = logging.getLogger(__name__)

class AlertServiceUnavailable(Exception):
    """Raised when the NWS service cannot be reached or returns invalid data."""
    pass

def fetch_json(url: str, headers: Dict[str, str], timeout: int = 8) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if not response.url.startswith("https://api.weather.gov/"):
                raise AlertServiceUnavailable(f"Redirected to unexpected host: {response.url}")
            
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise AlertServiceUnavailable("Response exceeds 2 MB limit")
                
            return json.loads(raw.decode("utf-8"))
    except HTTPError as e:
        if e.code in (400, 404):
            # Pass exactly this for location errors
            raise ValueError("That location is not covered by the National Weather Service.")
        raise AlertServiceUnavailable(f"HTTP Error: {e.code}")
    except URLError as e:
        raise AlertServiceUnavailable(f"Connection Error: {e.reason}")
    except json.JSONDecodeError as e:
        raise AlertServiceUnavailable(f"Invalid JSON: {e}")
    except Exception as e:
        if isinstance(e, ValueError) and "National Weather Service" in str(e):
            raise
        raise AlertServiceUnavailable(f"Unexpected Error: {e}")

def sanitize(text: Optional[str], max_length: int = 300) -> Optional[str]:
    if not text:
        return None
    # Remove control characters but keep newlines as spaces
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'[^\x20-\x7E]', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_length]

def parse_nws_features(payload: Dict[str, Any], now: str) -> List[Alert]:
    alerts = []
    features = payload.get("features", [])
    if not isinstance(features, list):
        logger.error("Features is not a list")
        return []
        
    for feature in features:
        try:
            props = feature.get("properties")
            if not props or not isinstance(props, dict):
                raise ValueError("Missing or invalid properties")
                
            status = props.get("status")
            if status != "Actual":
                continue
                
            msg_type = props.get("messageType")
            if msg_type == "Cancel":
                continue
                
            ends = props.get("ends") or props.get("expires")
            if ends and ends < now:
                continue
                
            event = props.get("event", "Unknown Event")
            event_lower = event.lower()
            
            if "flood" in event_lower:
                hazard = "flood"
            elif any(w in event_lower for w in ["hurricane", "tropical storm", "typhoon"]):
                hazard = "cyclone"
            elif "heat" in event_lower:
                hazard = "heat"
            elif any(w in event_lower for w in ["freeze", "frost", "cold", "wind chill", "winter", "blizzard", "ice"]):
                hazard = "cold"
            elif "earthquake" in event_lower:
                hazard = "earthquake"
            elif any(w in event_lower for w in ["fire", "red flag"]):
                hazard = "wildfire"
            elif any(w in event_lower for w in ["tornado", "thunderstorm", "wind", "hail"]):
                hazard = "storm"
            else:
                hazard = "other"
                
            if "Emergency" in event:
                severity = "emergency"
            elif event.endswith("Warning"):
                severity = "warning"
            elif event.endswith("Watch"):
                severity = "watch"
            else:
                severity = "advisory"
                
            id_val = props.get("id")
            sent = props.get("sent", "")
            if not id_val:
                id_val = hashlib.sha256(f"{event}{sent}".encode()).hexdigest()
                
            headline = props.get("headline") or event
            headline = sanitize(headline, 300)
            
            instructions = sanitize(props.get("instruction"), 1500)
            area_desc = sanitize(props.get("areaDesc"), 300)
            source = "National Weather Service"
            if props.get("senderName"):
                source += f" {props.get('senderName')}"
                
            alerts.append(Alert(
                id=str(id_val),
                hazard=hazard,
                severity=severity,
                headline=headline or "",
                area_description=area_desc or "",
                issued_at=str(sent),
                source=source,
                instructions=instructions,
                expires_at=ends
            ))
            
        except Exception as e:
            logger.error(f"Skipping malformed feature: {e}")
            
    return alerts

class NWSAlertProvider(AlertProvider):
    def __init__(self, point: str, fetcher: Callable = fetch_json, clock: Callable = time.time):
        self.name = "nws"
        self.data_mode = "live"
        self.is_simulated = False
        self.fetcher = fetcher
        self.clock = clock
        
        try:
            parts = point.split(",")
            if len(parts) != 2:
                raise ValueError()
            lat = round(float(parts[0]), 4)
            lon = round(float(parts[1]), 4)
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                raise ValueError()
            self.lat = lat
            self.lon = lon
        except ValueError:
            raise ValueError("Invalid NWS point. Must be lat,lon in valid ranges.")
            
        self._cache = None
        self._cache_time = 0

    def get_alerts(self) -> List[Alert]:
        now = self.clock()
        if self._cache is not None and (now - self._cache_time) < 60:
            return self._cache
            
        import os
        contact = os.environ.get("RISE_CONTACT", "no-contact-set")
        headers = {
            "Accept": "application/geo+json",
            "User-Agent": f"RISE-hackathon-demo ({contact})"
        }
        url = f"https://api.weather.gov/alerts/active?point={self.lat},{self.lon}"
        
        try:
            payload = self.fetcher(url, headers)
            if not isinstance(payload, dict) or "features" not in payload:
                raise AlertServiceUnavailable("Unexpected structure: missing 'features' list")
        except Exception as e:
            if isinstance(e, ValueError) and "National Weather Service" in str(e):
                raise
            logger.error(f"Failed to fetch NWS alerts: {e}")
            raise AlertServiceUnavailable("The live alert service could not be reached. Do not assume there are no active alerts. Check weather.gov or your local authorities.")
            
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        alerts = parse_nws_features(payload, now_iso)
        
        # Attach retrieved_at
        for a in alerts:
            a.retrieved_at = now_iso
            
        self.retrieved_at = now_iso
        self._cache = alerts
        self._cache_time = now
        return alerts

class RecordedAlertProvider(AlertProvider):
    def __init__(self, recording_name: str, fixtures_dir=None):
        self.name = "nws_recorded"
        self.data_mode = "recorded"
        self.is_simulated = False
        if not re.match(r'^[a-z0-9_]+$', recording_name):
            raise ValueError("Invalid recording name")
            
        from pathlib import Path
        self.fixtures_dir = fixtures_dir if fixtures_dir else Path(__file__).parent.parent / "fixtures" / "recorded"
        self.filepath = self.fixtures_dir / f"nws_{recording_name}.json"

    def get_alerts(self) -> List[Alert]:
        if not self.filepath.exists():
            raise ValueError(f"Recording not found: {self.filepath.name}")
            
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        recorded_at = data.get("recorded_at", "")
        payload = data.get("payload", {})
        
        alerts = parse_nws_features(payload, recorded_at)
        self.retrieved_at = recorded_at
        return alerts
