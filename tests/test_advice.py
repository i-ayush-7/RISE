import unittest
import os
from pathlib import Path
from rise.alerts import Alert
from rise.advice import build_advice
from rise.db import init_db
from rise.repository import Repository
import rise.tools

class TestAdvice(unittest.TestCase):
    def test_flood_warning_complex(self):
        plan = {
            "name": "Fam",
            "members": [
                {"name": "Gramps", "age_group": "senior", "support_level": "needs_assistance", "mobility_needs": "uses cane", "medical_needs": "meds", "is_pet": 0},
                {"name": "Kid", "age_group": "child", "support_level": "dependent", "is_pet": 0},
                {"name": "Dog", "age_group": "pet", "support_level": "dependent", "is_pet": 1}
            ],
            "contacts": [{"name": "Doc", "priority": 1}],
            "meeting_points": [{"label": "Park", "kind": "primary"}]
        }
        alerts = [
            Alert("1", "flood", "warning", "Head", "Area", "2026", "Src", "Go away")
        ]
        res = build_advice(plan, alerts, True)
        self.assertEqual(res["urgency"], "high")
        self.assertTrue(res["headline"].startswith("This is a simulated alert."))
        self.assertEqual(len(res["official_instructions"]), 1)
        self.assertEqual(res["official_instructions"][0]["instructions"], "Go away")
        
        actions = res["actions"]
        self.assertTrue(any(a["action"] == "Start moving Gramps early and arrange transport" and a["reason"] == "uses cane" for a in actions))
        self.assertTrue(any(a["action"] == "Keep an adult with Kid" for a in actions))
        self.assertTrue(any(a["action"] == "Gather pet supplies and a carrier for Dog" for a in actions))
        self.assertTrue(any(a["action"] == "Head to the primary meeting point: Park" for a in actions))
        self.assertTrue(any(a["action"] == "Call Doc first (priority 1)" for a in actions))
        
    def test_flood_watch(self):
        plan = {
            "name": "Fam",
            "members": [{"name": "John", "age_group": "adult", "support_level": "independent", "medical_needs": "meds", "is_pet": 0}],
            "meeting_points": [{"label": "Park", "kind": "primary"}]
        }
        alerts = [Alert("1", "flood", "watch", "Head", "Area", "2026", "Src")]
        res = build_advice(plan, alerts, False)
        self.assertEqual(res["urgency"], "low")
        actions = res["actions"]
        self.assertTrue(any("Review meeting point: Park" in a["action"] for a in actions))
        self.assertTrue(any("Gather John's medication" in a["action"] for a in actions))
        
    def test_heat_warning(self):
        plan = {
            "members": [
                {"name": "Gramps", "age_group": "senior", "support_level": "independent", "is_pet": 0},
                {"name": "Dog", "age_group": "pet", "support_level": "dependent", "is_pet": 1}
            ]
        }
        alerts = [Alert("1", "heat", "warning", "Head", "Area", "2026", "Src")]
        res = build_advice(plan, alerts, False)
        actions = res["actions"]
        self.assertTrue(any("cool and hydrated" in a["action"] for a in actions))
        self.assertTrue(any("shade and water for Dog" in a["action"] for a in actions))
        
    def test_cold_warning(self):
        plan = {
            "members": [{"name": "Kid", "age_group": "child", "support_level": "dependent", "is_pet": 0}]
        }
        alerts = [Alert("1", "cold", "warning", "Head", "Area", "2026", "Src")]
        res = build_advice(plan, alerts, False)
        self.assertTrue(any("keep them warm" in a["action"] for a in res["actions"]))
        
    def test_earthquake(self):
        plan = {
            "members": [{"name": "Gramps", "age_group": "senior", "support_level": "needs_assistance", "mobility_needs": "cane", "is_pet": 0}]
        }
        alerts = [Alert("1", "earthquake", "warning", "Head", "Area", "2026", "Src")]
        res = build_advice(plan, alerts, False)
        self.assertTrue(any("Drop, cover and hold on" in a["action"] for a in res["actions"]))
        self.assertTrue(any("Check on Gramps" in a["action"] for a in res["actions"]))
        
    def test_no_alerts(self):
        res = build_advice({"name": "Fam"}, [], False)
        self.assertEqual(res["urgency"], "none")
        self.assertEqual(res["headline"], "No active alerts for Fam.")
        self.assertEqual(len(res["actions"]), 0)
        
    def test_pet_only(self):
        plan = {"members": [{"name": "Dog", "age_group": "pet", "support_level": "dependent", "is_pet": 1}]}
        res = build_advice(plan, [Alert("1", "flood", "warning", "Head", "Area", "2026", "Src")], False)
        self.assertTrue(any("Gather pet supplies" in a["action"] for a in res["actions"]))
        
    def test_no_contacts_or_meeting_points(self):
        plan = {"members": [{"name": "John", "is_pet": 0, "support_level": "independent"}]}
        res = build_advice(plan, [Alert("1", "flood", "warning", "Head", "Area", "2026", "Src")], False)
        self.assertTrue(any("Choose a safe place to go" in a["action"] for a in res["actions"]))
        
    def test_multiple_alerts_dedup(self):
        plan = {"members": [{"name": "John", "is_pet": 0, "support_level": "independent"}]}
        alerts = [
            Alert("1", "flood", "watch", "H1", "A", "20", "S"),
            Alert("2", "flood", "warning", "H2", "A", "20", "S")
        ]
        res = build_advice(plan, alerts, False)
        # Should use highest severity (warning)
        self.assertEqual(res["urgency"], "high")
        
    def test_identical_input(self):
        plan = {"members": [{"name": "John", "is_pet": 0, "support_level": "independent"}]}
        alerts = [Alert("1", "storm", "warning", "H1", "A", "20", "S")]
        res1 = build_advice(plan, alerts, False)
        res2 = build_advice(plan, alerts, False)
        self.assertEqual(res1, res2)

    def test_imports_clean(self):
        with open("rise/advice.py", "r") as f:
            content = f.read()
        for banned in ["urllib", "http", "socket", "requests", "httpx", "ssl"]:
            self.assertNotIn(f"import {banned}", content)
            self.assertNotIn(f"from {banned}", content)
            
        with open("rise/alerts.py", "r") as f:
            content = f.read()
        for banned in ["urllib", "http", "socket", "requests", "httpx", "ssl"]:
            self.assertNotIn(f"import {banned}", content)
            self.assertNotIn(f"from {banned}", content)

    def test_tool_end_to_end(self):
        db_path = Path(__file__).parent / "test_advice_db.db"
        if db_path.exists():
            db_path.unlink()
        init_db(db_path)
        repo = Repository(db_path)
        
        old_db = os.environ.get("RISE_DB_PATH")
        os.environ["RISE_DB_PATH"] = str(db_path)
        os.environ["RISE_ALERT_SOURCE"] = "fixture"
        os.environ["RISE_FIXTURE_SCENARIO"] = "flood_warning"
        
        try:
            h = repo.create_household("Test Fam")
            rise.tools.add_member("John", "adult", "independent", household_id=h.id)
            
            res = rise.tools.get_safety_advice(h.id)
            self.assertEqual(res["urgency"], "high")
            self.assertTrue(res["is_simulated"])
        finally:
            if old_db is None:
                del os.environ["RISE_DB_PATH"]
            else:
                os.environ["RISE_DB_PATH"] = old_db
            if db_path.exists():
                db_path.unlink()

if __name__ == "__main__":
    unittest.main()
