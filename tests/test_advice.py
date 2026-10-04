import unittest
import os
from pathlib import Path
from unittest.mock import patch
from rise.alerts import Alert
from rise.advice import build_advice
from rise.db import init_db
from rise.repository import Repository
import rise.tools

class TestAdvice(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {})
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

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
        self.assertFalse(any("Start moving" in a["action"] for a in actions))
        
    def test_heat_warning(self):
        plan = {
            "name": "Fam",
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
        self.assertIn("need extra care", res["headline"])
        self.assertNotIn("getting out", res["headline"])
        
    def test_cold_warning(self):
        plan = {
            "name": "Fam",
            "members": [{"name": "Kid", "age_group": "child", "support_level": "dependent", "is_pet": 0}]
        }
        alerts = [Alert("1", "cold", "warning", "Head", "Area", "2026", "Src")]
        res = build_advice(plan, alerts, False)
        self.assertTrue(any("keep them warm" in a["action"] for a in res["actions"]))
        
    def test_earthquake(self):
        plan = {
            "name": "Fam",
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
        plan = {"name": "Fam", "members": [{"name": "Dog", "age_group": "pet", "support_level": "dependent", "is_pet": 1}]}
        res = build_advice(plan, [Alert("1", "flood", "warning", "Head", "Area", "2026", "Src")], False)
        self.assertTrue(any("Gather pet supplies" in a["action"] for a in res["actions"]))
        
    def test_no_contacts_or_meeting_points(self):
        plan = {"name": "Fam", "members": [{"name": "John", "is_pet": 0, "support_level": "independent"}]}
        res = build_advice(plan, [Alert("1", "flood", "warning", "Head", "Area", "2026", "Src")], False)
        self.assertTrue(any("Choose a safe place to go" in a["action"] for a in res["actions"]))
        
    def test_multiple_alerts_dedup(self):
        plan = {"name": "Fam", "members": [{"name": "John", "is_pet": 0, "support_level": "independent"}]}
        alerts = [
            Alert("1", "flood", "watch", "H1", "A", "20", "S"),
            Alert("2", "flood", "warning", "H2", "A", "20", "S")
        ]
        res = build_advice(plan, alerts, False)
        # Should use highest severity (warning)
        self.assertEqual(res["urgency"], "high")
        
    def test_identical_input(self):
        plan = {"name": "Fam", "members": [{"name": "John", "is_pet": 0, "support_level": "independent"}]}
        alerts = [Alert("1", "storm", "warning", "H1", "A", "20", "S")]
        res1 = build_advice(plan, alerts, False)
        res2 = build_advice(plan, alerts, False)
        self.assertEqual(res1, res2)

    def test_storm_warning(self):
        plan = {"name": "Fam", "members": [{"name": "John", "is_pet": 0, "support_level": "independent"}]}
        alerts = [Alert("1", "storm", "warning", "H1", "A", "20", "S")]
        res = build_advice(plan, alerts, False)
        self.assertTrue(any("Stay indoors and keep phones charged" in a["action"] for a in res["actions"]))

    def test_storm_watch(self):
        plan = {"name": "Fam", "members": [{"name": "John", "is_pet": 0, "support_level": "independent"}]}
        alerts = [Alert("1", "storm", "watch", "H1", "A", "20", "S")]
        res = build_advice(plan, alerts, False)
        self.assertTrue(any("Keep phones charged and watch for updates" in a["action"] for a in res["actions"]))

    def test_flood_warning_heat_warning(self):
        plan = {"name": "Fam", "members": [{"name": "Gramps", "age_group": "senior", "is_pet": 0, "support_level": "independent"}]}
        alerts = [
            Alert("1", "flood", "warning", "Flood", "A", "20", "S", instructions="Run"),
            Alert("2", "heat", "warning", "Heat", "A", "20", "S", instructions="Stay")
        ]
        res = build_advice(plan, alerts, False)
        actions = res["actions"]
        self.assertFalse(any("cool and hydrated" in a["action"] for a in actions)) # no heat actions
        self.assertIn("heat", res["headline"])
        self.assertEqual(len(res["official_instructions"]), 2)

    def test_action_cap(self):
        plan = {
            "name": "Fam",
            "members": [
                {"name": f"P{i}", "age_group": "adult", "is_pet": 0, "support_level": "needs_assistance"} for i in range(7)
            ] + [{"name": "Dog", "age_group": "pet", "is_pet": 1, "support_level": "dependent"}],
            "contacts": [{"name": "Doc", "priority": 1}],
            "meeting_points": [{"label": "Park", "kind": "primary"}]
        }
        # Candidates: 7 adults * P1 = 7. 1 MP = P3. 1 Contact = P4. 1 Pet = P6, P7. Total = 11.
        alerts = [Alert("1", "flood", "warning", "H1", "A", "20", "S")]
        res = build_advice(plan, alerts, False)
        self.assertEqual(len(res["actions"]), 8)
        actions = res["actions"]
        self.assertTrue(any("Call Doc first" in a["action"] for a in actions))
        self.assertTrue(any("Head to the primary meeting point" in a["action"] for a in actions))
        priorities = [a["priority"] for a in actions]
        self.assertEqual(priorities, sorted(priorities))

    def test_earthquake_in_evac_mode(self):
        plan = {
            "name": "Fam",
            "members": [{"name": "A", "is_pet": 0, "support_level": "independent"}]
        }
        alerts = [
            Alert("1", "flood", "warning", "H1", "A", "20", "S", ""),
            Alert("2", "earthquake", "warning", "H2", "A", "20", "S", "")
        ]
        res = build_advice(plan, alerts, False)
        self.assertEqual(res["actions"][0]["action"], "Drop, cover and hold on")
        self.assertEqual(res["actions"][0]["priority"], 0)
        self.assertTrue(any("Choose a safe place" in a["action"] for a in res["actions"]))
        self.assertTrue(len(res["actions"]) <= 8)

    def test_earthquake_help_count(self):
        plan = {
            "name": "Fam",
            "members": [
                {"name": "A", "is_pet": 0, "support_level": "needs_assistance"},
                {"name": "B", "is_pet": 0, "support_level": "independent"},
            ]
        }
        alerts = [Alert("1", "earthquake", "warning", "H1", "A", "20", "S", "")]
        res = build_advice(plan, alerts, False)
        check_on_actions = [a for a in res["actions"] if a["action"].startswith("Check on")]
        self.assertEqual(len(check_on_actions), 1)
        self.assertIn("1 person may need help after the shaking stops", res["headline"])

    def test_two_evacuation_hazards(self):
        plan = {
            "name": "Fam",
            "members": [{"name": "A", "is_pet": 0, "support_level": "independent"}]
        }
        alerts = [
            Alert("1", "flood", "warning", "H1", "A", "20", "S", ""),
            Alert("2", "wildfire", "emergency", "H2", "A", "20", "S", "")
        ]
        res = build_advice(plan, alerts, False)
        head_actions = [a for a in res["actions"] if "Choose a safe place to go" in a["action"]]
        self.assertEqual(len(head_actions), 1)

    def test_action_sorting(self):
        plan = {
            "name": "Fam",
            "members": [
                {"name": "A", "age_group": "adult", "is_pet": 0, "support_level": "needs_assistance"},
                {"name": "B", "age_group": "child", "is_pet": 0, "support_level": "dependent"}
            ],
            "contacts": [{"name": "Doc", "priority": 1}],
            "meeting_points": [{"label": "Park", "kind": "primary"}]
        }
        alerts = [Alert("1", "flood", "warning", "H1", "A", "20", "S")]
        res = build_advice(plan, alerts, False)
        priorities = [a["priority"] for a in res["actions"]]
        self.assertEqual(priorities, sorted(priorities))

    def test_headline_capitalization(self):
        plan = {"name": "Fam", "members": []}
        alerts = [Alert("1", "flood", "warning", "H1", "A", "20", "S"), Alert("2", "storm", "watch", "H2", "A", "20", "S")]
        res = build_advice(plan, alerts, False)
        self.assertEqual(res["headline"], "Flood warning and storm watch for Fam.")

    def test_imports_clean(self):
        with open(Path(__file__).parent.parent / "rise" / "advice.py", "r") as f:
            content = f.read()
        for banned in ["urllib", "http", "socket", "requests", "httpx", "ssl"]:
            self.assertNotIn(f"import {banned}", content)
            self.assertNotIn(f"from {banned}", content)
            
        with open(Path(__file__).parent.parent / "rise" / "alerts.py", "r") as f:
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
            if db_path.exists():
                db_path.unlink()

    def test_rivera_scenario(self):
        db_path = Path(__file__).parent / "test_advice_db.db"
        if db_path.exists():
            db_path.unlink()
        
        os.environ["RISE_DB_PATH"] = str(db_path)
        os.environ["RISE_ALERT_SOURCE"] = "fixture"
        os.environ["RISE_FIXTURE_SCENARIO"] = "flood_warning"
        
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "rise.seed"], check=True, env=os.environ)
        
        try:
            res = rise.tools.get_safety_advice(1)
            actions = res["actions"]
            action_texts = [a["action"] for a in actions]
            
            self.assertIn("Start moving Elena Rivera early and arrange transport", action_texts)
            self.assertIn("Keep an adult with Leo Rivera", action_texts)
            self.assertIn("Head to the primary meeting point: Neighborhood Park", action_texts)
            self.assertIn("Call Uncle Juan first (priority 1)", action_texts)
            self.assertIn("Gather Elena Rivera's medication and documents", action_texts)
            
            self.assertFalse(any("Stay indoors" in a for a in action_texts))
            self.assertFalse(any("Start moving Leo" in a for a in action_texts))
            self.assertTrue(len(actions) <= 8)
            
            # The headline based on code output - Leo is support_level='dependent', so he's counted!
            self.assertEqual(res["headline"], "This is a simulated alert. Flood warning and storm watch for The Rivera Family: 2 people need extra help getting out.")
        finally:
            if db_path.exists():
                db_path.unlink()

if __name__ == "__main__":
    unittest.main()
