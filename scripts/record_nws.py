import os
import argparse
import json
import datetime
from pathlib import Path

# Add project root to sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from rise.nws import fetch_json

def main():
    parser = argparse.ArgumentParser(description="Record NWS alerts to a fixture file.")
    parser.add_argument("--point", help="lat,lon to fetch")
    parser.add_argument("--area", help="Two letter state code (e.g. TX)")
    parser.add_argument("--name", required=True, help="Name for the recording")
    
    args = parser.parse_args()
    
    import re
    if not re.match(r'^[a-z0-9_]+$', args.name):
        raise ValueError("Invalid recording name")
        
    if args.point:
        parts = args.point.split(",")
        lat, lon = round(float(parts[0]), 4), round(float(parts[1]), 4)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValueError("Invalid coordinates")
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
    elif args.area:
        url = f"https://api.weather.gov/alerts/active?area={args.area}"
    else:
        raise ValueError("Must provide either --point or --area")
        
    headers = {
        "Accept": "application/geo+json",
        "User-Agent": f"RISE-hackathon-demo ({os.environ.get('RISE_CONTACT', 'no-contact-set')})"
    }
    
    print(f"Fetching from {url} ...")
    payload = fetch_json(url, headers)
    
    recorded_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output = {
        "recorded_at": recorded_at,
        "payload": payload
    }
    
    out_dir = Path(__file__).parent.parent / "fixtures" / "recorded"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"nws_{args.name}.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
        
    print(f"Saved {len(payload.get('features', []))} alerts to {out_file.name}")

if __name__ == "__main__":
    main()
