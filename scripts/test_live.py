import os
import json
from rise.tools import get_active_alerts, get_safety_advice, _load_plan

def main():
    # Setup test household
    from rise.repository import Repository
    from rise.db import init_db
    import rise.tools
    
    db_path = "test_run.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    repo = Repository(db_path)
    
    os.environ["RISE_DB_PATH"] = db_path
    os.environ["RISE_ALERT_SOURCE"] = "nws"
    os.environ["RISE_NWS_POINT"] = "30.7,-86.5"
    
    h = repo.create_household("Live Fam")
    rise.tools.add_member("A", "adult", "independent", household_id=h.id)
    
    print("--- get_active_alerts ---")
    alerts_data = get_active_alerts(h.id)
    print("data_mode:", alerts_data["data_mode"])
    print("source:", alerts_data["source"])
    print("retrieved_at:", alerts_data["retrieved_at"])
    print("number of alerts:", len(alerts_data["alerts"]))
    print("events:", [a["hazard"] + " " + a["severity"] for a in alerts_data["alerts"]])
    
    print("\n--- get_safety_advice ---")
    advice_data = get_safety_advice(h.id)
    print("data_mode:", advice_data["data_mode"])
    print("source:", advice_data["source"])
    print("retrieved_at:", advice_data["retrieved_at"])
    
if __name__ == "__main__":
    main()
