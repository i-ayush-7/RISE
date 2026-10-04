import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

from rise.tools import get_household_plan, _now
from rise.escalation import build_escalation
from rise.repository import Repository
import rise.tools

def run_demo():
    real_db = Path("data/rise.db")
    mtime_before = real_db.stat().st_mtime if real_db.exists() else None
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = Path(f.name)
        
    try:
        env = os.environ.copy()
        env["RISE_DB_PATH"] = str(temp_db_path)
        
        subprocess.run([sys.executable, "-m", "rise.seed"], env=env, check=True, capture_output=True)
        
        os.environ["RISE_DB_PATH"] = str(temp_db_path)
        plan = get_household_plan(1)
        
        started_at = datetime.fromisoformat("2026-10-05T00:00:00+00:00")
        
        print("=== SCENARIO 1: Elena, Leo, Buddy pending ===")
        members_state = []
        for m in plan.get("members", []):
            st = "safe" if m["name"] in ("Maria Rivera", "Carlos Rivera") else "pending"
            members_state.append({
                "member_id": m["id"],
                "name": m["name"],
                "is_pet": m["is_pet"],
                "status": st,
                "note": ""
            })
            
        state1 = {
            "started_at": started_at.isoformat(),
            "members": members_state
        }
        
        for minutes in [0, 6, 12, 25]:
            now = started_at + timedelta(minutes=minutes)
            res = build_escalation(plan, state1, now)
            print(f"\n--- At {minutes} minutes ---")
            print(json.dumps(res, indent=2))
            
        print("\n=== SCENARIO 2: Elena needs help at 3 minutes ===")
        members_state2 = []
        for m in plan.get("members", []):
            st = "safe" if m["name"] in ("Maria Rivera", "Carlos Rivera") else "pending"
            note = ""
            if m["name"] == "Elena Rivera":
                st = "needs_help"
                note = "fell and cannot stand"
            members_state2.append({
                "member_id": m["id"],
                "name": m["name"],
                "is_pet": m["is_pet"],
                "status": st,
                "note": note
            })
            
        state2 = {
            "started_at": started_at.isoformat(),
            "members": members_state2
        }
        
        now2 = started_at + timedelta(minutes=3)
        res2 = build_escalation(plan, state2, now2)
        print(f"\n--- At 3 minutes ---")
        print(json.dumps(res2, indent=2))
        
        print("\n=== SCENARIO 3: Elena needs help at 12 minutes ===")
        members_state3 = []
        for m in plan.get("members", []):
            st = "safe" if m["name"] in ("Maria Rivera", "Carlos Rivera", "Leo Rivera") else "pending"
            note = ""
            if m["name"] == "Elena Rivera":
                st = "needs_help"
                note = "fell and cannot stand"
            members_state3.append({
                "member_id": m["id"],
                "name": m["name"],
                "is_pet": m["is_pet"],
                "status": st,
                "note": note
            })
            
        state3 = {
            "started_at": started_at.isoformat(),
            "members": members_state3
        }
        
        now3 = started_at + timedelta(minutes=12)
        res3 = build_escalation(plan, state3, now3)
        print(f"\n--- At 12 minutes ---")
        print(json.dumps(res3, indent=2))
        
    finally:
        if temp_db_path.exists():
            try:
                temp_db_path.unlink()
            except Exception:
                pass
                
    mtime_after = real_db.stat().st_mtime if real_db.exists() else None
    
    print("\n--- DB Modification Check ---")
    print(f"data/rise.db existed before: {mtime_before is not None}")
    print(f"data/rise.db modified time before: {mtime_before}")
    print(f"data/rise.db modified time after:  {mtime_after}")
    print(f"Unchanged: {mtime_before == mtime_after}")

if __name__ == "__main__":
    run_demo()
