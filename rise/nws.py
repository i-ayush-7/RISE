import json
import logging
import time
import urllib.request
import socket
import datetime
from typing import List, Optional, Callable, Dict, Any
from urllib.error import URLError, HTTPError
from rise.alerts import Alert, AlertProvider
import hashlib
import re
import unicodedata

logger = logging.getLogger(__name__)

class AlertServiceUnavailable(Exception):
    """Raised when the NWS service cannot be reached or returns invalid data."""
    pass

_CACHE = {}

def clear_cache():
    _CACHE.clear()

def parse_time(s: str) -> Optional[datetime.datetime]:
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None

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
            raise ValueError("That location is not covered by the National Weather Service.")
        raise AlertServiceUnavailable(f"HTTP Error: {e.code}")
    except URLError as e:
        if isinstance(e.reason, socket.timeout):
            raise AlertServiceUnavailable("Connection Error: timeout")
        raise AlertServiceUnavailable(f"Connection Error: {e.reason}")
    except socket.timeout:
        raise AlertServiceUnavailable("Connection Error: timeout")
    except json.JSONDecodeError as e:
        raise AlertServiceUnavailable(f"Invalid JSON: {e}")
    except Exception as e:
        if isinstance(e, ValueError) and "National Weather Service" in str(e):
            raise
        raise AlertServiceUnavailable(f"Unexpected Error: {e}")

def sanitize(text: Optional[str], max_length: int = 300) -> Optional[str]:
    if not text:
        return None
    chars = []
    for c in text:
        cat = unicodedata.category(c)
        if c in ('\n', '\r', '\t'):
            chars.append(' ')
        elif cat == 'Cc':
            continue
        elif cat == 'Cf':
            continue
        else:
            chars.append(c)
            
    text = "".join(chars)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_length]

def parse_nws_features(payload: Dict[str, Any], now: datetime.datetime) -> List[Alert]:
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
                
            end_str = props.get("ends") or props.get("expires")
            if end_str:
                end_dt = parse_time(end_str)
                if end_dt is not None:
                    if end_dt <= now:
                        continue
                else:
                    logger.warning(f"Unparseable end time: {end_str}, keeping alert.")
                
            event = props.get("event", "Unknown Event")
            event_lower = event.lower()
            
            if "tsunami" in event_lower:
                hazard = "other"
            elif "evacuation" in event_lower or "shelter in place" in event_lower:
                hazard = "other"
            elif "flood" in event_lower:
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
                
            if "tsunami" in event_lower or "evacuation" in event_lower or "shelter in place" in event_lower:
                severity = "warning"
                if "Emergency" in event:
                    severity = "emergency"
            else:
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
                expires_at=end_str
            ))
            
        except Exception as e:
            logger.error(f"Skipping malformed feature: {e}")
            
    return alerts

class NWSAlertProvider(AlertProvider):
    def __init__(self, point: str, fetcher: Optional[Callable] = None, clock: Optional[Callable] = None):
        self.name = "nws"
        self.data_mode = "live"
        self.is_simulated = False
        self.fetcher = fetcher or fetch_json
        self.clock = clock or time.time
        
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

    def get_alerts(self) -> List[Alert]:
        now_ts = self.clock()
        now_dt = datetime.datetime.fromtimestamp(now_ts, datetime.timezone.utc)
        
        cache_key = (self.lat, self.lon)
        if cache_key in _CACHE:
            entry = _CACHE[cache_key]
            if now_ts - entry["time"] < 60:
                self.retrieved_at = entry["retrieved_at"]
                return entry["alerts"]
            
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
            
        now_iso = now_dt.isoformat()
        alerts = parse_nws_features(payload, now_dt)
        
        for a in alerts:
            a.retrieved_at = now_iso
            
        self.retrieved_at = now_iso
        _CACHE[cache_key] = {
            "time": now_ts,
            "retrieved_at": now_iso,
            "alerts": alerts
        }
        return alerts

class RecordedAlertProvider(AlertProvider):
    def __init__(self, recording_name: str, fixtures_dir=None):
        self.name = "nws_recorded"
        self.data_mode = "recorded"
        self.is_simulated = False
        import re
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
            
        recorded_at_str = data.get("recorded_at", "")
        recorded_at_dt = parse_time(recorded_at_str)
        if recorded_at_dt is None:
            raise ValueError("Recording is invalid: bad recorded_at")
            
        payload = data.get("payload", {})
        
        alerts = parse_nws_features(payload, recorded_at_dt)
        self.retrieved_at = recorded_at_str
        return alerts
