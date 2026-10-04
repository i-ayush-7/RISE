import json
from datetime import datetime, timedelta
from rise.escalation import build_escalation

def run_demo():
    rivera_plan = {
        "name": "The Rivera Family",
        "members": [
            {"name": "Maria", "is_pet": 0, "support_level": "independent", "mobility_needs": ""},
            {"name": "Carlos", "is_pet": 0, "support_level": "independent", "mobility_needs": ""},
            {"name": "Elena", "is_pet": 0, "support_level": "needs_assistance", "mobility_needs": "Uses a cane", "medical_needs": "High blood pressure medication"},
            {"name": "Leo", "is_pet": 0, "support_level": "dependent", "mobility_needs": ""},
            {"name": "Buddy", "is_pet": 1, "support_level": "dependent", "mobility_needs": ""}
        ],
        "contacts": [
            {"name": "Uncle Juan", "priority": 1, "phone": "555-0199"},
            {"name": "Aunt Rosa", "priority": 2, "phone": "555-0200"}
        ]
    }

    started_at = datetime.fromisoformat("2026-10-05T00:00:00+00:00")

    print("=== SCENARIO 1: Elena, Leo, Buddy pending ===")
    state1 = {
        "started_at": started_at.isoformat(),
        "members": [
            {"name": "Maria", "is_pet": 0, "status": "safe", "note": ""},
            {"name": "Carlos", "is_pet": 0, "status": "safe", "note": ""},
            {"name": "Elena", "is_pet": 0, "status": "pending", "note": ""},
            {"name": "Leo", "is_pet": 0, "status": "pending", "note": ""},
            {"name": "Buddy", "is_pet": 1, "status": "pending", "note": ""}
        ]
    }
    
    for minutes in [0, 6, 12, 25]:
        now = started_at + timedelta(minutes=minutes)
        res = build_escalation(rivera_plan, state1, now)
        print(f"\n--- At {minutes} minutes ---")
        print(json.dumps(res, indent=2))
        
    print("\n=== SCENARIO 2: Elena needs help at 3 minutes ===")
    state2 = {
        "started_at": started_at.isoformat(),
        "members": [
            {"name": "Maria", "is_pet": 0, "status": "safe", "note": ""},
            {"name": "Carlos", "is_pet": 0, "status": "safe", "note": ""},
            {"name": "Elena", "is_pet": 0, "status": "needs_help", "note": "fell and cannot stand"},
            {"name": "Leo", "is_pet": 0, "status": "pending", "note": ""},
            {"name": "Buddy", "is_pet": 1, "status": "pending", "note": ""}
        ]
    }
    now2 = started_at + timedelta(minutes=3)
    res2 = build_escalation(rivera_plan, state2, now2)
    print(f"\n--- At 3 minutes ---")
    print(json.dumps(res2, indent=2))

if __name__ == "__main__":
    run_demo()
