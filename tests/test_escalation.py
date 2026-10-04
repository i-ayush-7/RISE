import unittest
import os
import ast
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

from rise.escalation import build_escalation
import rise.tools

class TestEscalation(unittest.TestCase):

    def setUp(self):
        self.now = datetime.fromisoformat("2026-10-05T00:00:00+00:00")
        
        self.rivera_plan = {
            "name": "The Rivera Family",
            "members": [
                {"id": 1, "name": "Maria", "is_pet": 0, "support_level": "independent", "mobility_needs": ""},
                {"id": 2, "name": "Carlos", "is_pet": 0, "support_level": "independent", "mobility_needs": ""},
                {"id": 3, "name": "Elena", "is_pet": 0, "support_level": "needs_assistance", "mobility_needs": "Uses a cane", "medical_needs": "High blood pressure medication"},
                {"id": 4, "name": "Leo", "is_pet": 0, "support_level": "dependent", "mobility_needs": ""},
                {"id": 5, "name": "Buddy", "is_pet": 1, "support_level": "dependent", "mobility_needs": ""}
            ],
            "contacts": [
                {"name": "Uncle Juan", "priority": 1, "phone": "555-0199"},
                {"name": "Aunt Rosa", "priority": 2, "phone": "555-0200"}
            ]
        }

    def _state_from_statuses(self, statuses, started_at_offset=0):
        members = []
        for name, status in statuses.items():
            pm = next((m for m in self.rivera_plan["members"] if m["name"] == name), None)
            is_pet = pm["is_pet"] if pm else (1 if name == "Buddy" else 0)
            m_id = pm["id"] if pm else 0
            members.append({
                "member_id": m_id,
                "name": name,
                "is_pet": is_pet,
                "status": status,
                "note": "fell and cannot stand" if status == "needs_help" else ""
            })
        return {
            "started_at": (self.now - timedelta(minutes=started_at_offset)).isoformat(),
            "members": members
        }

    def test_level_by_time(self):
        plan = {"members": [{"name": "A", "is_pet": 0}]}
        
        state = {"started_at": (self.now - timedelta(minutes=4)).isoformat(), "members": [{"name": "A", "is_pet": 0, "status": "pending"}]}
        self.assertEqual(build_escalation(plan, state, self.now)["level"], 0)
        
        state["started_at"] = (self.now - timedelta(minutes=5)).isoformat()
        self.assertEqual(build_escalation(plan, state, self.now)["level"], 1)
        
        state["started_at"] = (self.now - timedelta(minutes=9)).isoformat()
        self.assertEqual(build_escalation(plan, state, self.now)["level"], 1)
        
        state["started_at"] = (self.now - timedelta(minutes=10)).isoformat()
        self.assertEqual(build_escalation(plan, state, self.now)["level"], 2)
        
        state["started_at"] = (self.now - timedelta(minutes=19)).isoformat()
        self.assertEqual(build_escalation(plan, state, self.now)["level"], 2)
        
        state["started_at"] = (self.now - timedelta(minutes=20)).isoformat()
        self.assertEqual(build_escalation(plan, state, self.now)["level"], 3)

    def test_level_zero_if_everyone_safe(self):
        plan = {"members": [{"name": "A", "is_pet": 0}]}
        state = {"started_at": (self.now - timedelta(minutes=60)).isoformat(), "members": [{"name": "A", "is_pet": 0, "status": "safe"}]}
        self.assertEqual(build_escalation(plan, state, self.now)["level"], 0)

    def test_vulnerable_first_ordering(self):
        # 8 people total, 6 max. 2 are vulnerable.
        statuses = {f"Person{i}": "pending" for i in range(6)}
        statuses["Elena"] = "pending"
        statuses["Leo"] = "pending"
        state = self._state_from_statuses(statuses, 0)
        
        esc = build_escalation(self.rivera_plan, state, self.now)
        steps = esc["next_steps"]
        names = [s["who"] for s in steps if s["priority"] == 1 and s["who"] is not None]
        
        self.assertEqual(len(names), 6)
        self.assertIn("Elena", names)
        self.assertIn("Leo", names)
        
        more_steps = [s for s in steps if s["priority"] == 1 and s["who"] is None]
        self.assertEqual(len(more_steps), 1)
        self.assertTrue(more_steps[0]["action"].startswith("Also check on 2 more:"))

    def test_needs_help_produces_p0(self):
        state = self._state_from_statuses({"Elena": "needs_help"}, 0)
        esc = build_escalation(self.rivera_plan, state, self.now)
        steps = esc["next_steps"]
        self.assertEqual(steps[0]["action"], "If anyone is in immediate danger, call your local emergency number")
        self.assertEqual(steps[1]["action"], "Help Elena")
        self.assertEqual(steps[1]["reason"], "fell and cannot stand")

    def test_level_2_contacts_first_contact(self):
        state = self._state_from_statuses({"Maria": "pending"}, 10)
        esc = build_escalation(self.rivera_plan, state, self.now)
        p2_steps = [s for s in esc["next_steps"] if s["priority"] == 2]
        self.assertEqual(len(p2_steps), 1)
        self.assertEqual(p2_steps[0]["who"], "Uncle Juan")
        self.assertEqual(p2_steps[0]["reason"], "Phone: 555-0199")
        self.assertIn("Maria", p2_steps[0]["action"])

    def test_level_3_contacts_second_contact(self):
        state = self._state_from_statuses({"Maria": "pending"}, 20)
        esc = build_escalation(self.rivera_plan, state, self.now)
        p2_steps = [s for s in esc["next_steps"] if s["priority"] == 2]
        p3_steps = [s for s in esc["next_steps"] if s["priority"] == 3 and s["who"]]
        self.assertEqual(p2_steps[0]["who"], "Uncle Juan")
        self.assertEqual(p3_steps[0]["who"], "Aunt Rosa")

    def test_no_contacts_exact_wording(self):
        plan = {"name": "Fam", "members": [{"name": "A", "is_pet": 0}]}
        state = {"started_at": (self.now - timedelta(minutes=15)).isoformat(), "members": [{"name": "A", "is_pet": 0, "status": "pending"}]}
        esc = build_escalation(plan, state, self.now)
        p2_steps = [s for s in esc["next_steps"] if s["priority"] == 2]
        self.assertEqual(p2_steps[0]["action"], "No emergency contacts are saved. Ask a neighbor or local authorities to help check on A")

    def test_pets_not_safe_p5(self):
        state = self._state_from_statuses({"Buddy": "pending"})
        esc = build_escalation(self.rivera_plan, state, self.now)
        p5_steps = [s for s in esc["next_steps"] if s["priority"] == 5]
        self.assertEqual(p5_steps[0]["action"], "Confirm where Buddy is")

    def test_all_safe(self):
        state = self._state_from_statuses({"Maria": "safe", "Buddy": "safe"})
        esc = build_escalation(self.rivera_plan, state, self.now)
        self.assertTrue(esc["all_accounted_for"])
        self.assertEqual(esc["next_steps"][-1]["action"], "Everyone is confirmed safe. Close the check-in when you are ready.")

    def test_one_pending_among_safe(self):
        state = self._state_from_statuses({"Maria": "safe", "Carlos": "safe", "Buddy": "pending"})
        esc = build_escalation(self.rivera_plan, state, self.now)
        self.assertFalse(esc["all_accounted_for"])
        self.assertFalse(any(s["priority"] == 9 for s in esc["next_steps"]))

    def test_exact_speakable_strings(self):
        # Scenario 1: Rivera with Elena needs_help and Leo pending
        state1 = self._state_from_statuses({"Maria": "safe", "Carlos": "safe", "Elena": "needs_help", "Leo": "pending", "Buddy": "safe"})
        esc1 = build_escalation(self.rivera_plan, state1, self.now)
        self.assertEqual(esc1["speakable"], "2 of 4 people are confirmed safe. Elena needs help. Leo has not responded.")

        # Scenario 2: everyone safe
        state2 = self._state_from_statuses({"Maria": "safe", "Carlos": "safe", "Elena": "safe", "Leo": "safe", "Buddy": "safe"})
        esc2 = build_escalation(self.rivera_plan, state2, self.now)
        self.assertEqual(esc2["speakable"], "Everyone is confirmed safe.")

        # Scenario 3: nobody responded
        state3 = self._state_from_statuses({"Maria": "pending", "Carlos": "pending", "Elena": "pending", "Leo": "pending", "Buddy": "pending"})
        esc3 = build_escalation(self.rivera_plan, state3, self.now)
        # Note: 0 of 4 people are confirmed safe
        self.assertTrue(esc3["speakable"].startswith("0 of 4 people are confirmed safe."))
        self.assertIn("have not responded", esc3["speakable"])

    def test_draft_message_rivera(self):
        state = self._state_from_statuses({"Maria": "safe", "Carlos": "safe", "Elena": "needs_help", "Leo": "pending", "Buddy": "safe"})
        esc = build_escalation(self.rivera_plan, state, self.now)
        
        self.assertEqual(esc["draft_message"], "R.I.S.E. check-in for The Rivera Family. Safe: Maria and Carlos. Needs help: Elena (fell and cannot stand). Not yet reached: Leo. Please help check on Leo.")
        
        # ensure no medical/mobility text
        out = str(esc)
        self.assertNotIn("High blood pressure medication", out)
        self.assertNotIn("Uses a cane", out)

    def test_identical_input_identical_output(self):
        state = self._state_from_statuses({"Maria": "pending"})
        esc1 = build_escalation(self.rivera_plan, state, self.now)
        esc2 = build_escalation(self.rivera_plan, state, self.now)
        self.assertEqual(esc1, esc2)

    def test_purity_ast(self):
        path = Path(__file__).parent.parent / "rise" / "escalation.py"
        source = path.read_text("utf-8")
        
        # Test exact string bans
        self.assertNotIn("datetime.now", source)
        self.assertNotIn("utcnow", source)
        self.assertNotIn("time.time", source)
        
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    self.assertNotIn(name.name, ["sqlite3", "os", "socket", "urllib", "http", "ssl", "requests", "httpx", "time"])
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, ["sqlite3", "os", "socket", "urllib", "http", "ssl", "requests", "httpx", "time"])


    def test_join_names(self):
        from rise.escalation import build_escalation
        # Hack to access join_names, we can just test it by providing state
        # 1 name
        state = self._state_from_statuses({"Maria": "safe", "Buddy": "pending"}, 0)
        esc = build_escalation(self.rivera_plan, state, self.now)
        self.assertIn("1 of 1 person is confirmed safe", esc["speakable"])
        
        # 2 names
        state = self._state_from_statuses({"Maria": "safe", "Carlos": "safe"}, 0)
        esc = build_escalation(self.rivera_plan, state, self.now)
        self.assertIn("Safe: Maria and Carlos", esc["draft_message"])
        
        # 3 names
        state = self._state_from_statuses({"Maria": "safe", "Carlos": "safe", "Leo": "safe"}, 0)
        esc = build_escalation(self.rivera_plan, state, self.now)
        self.assertIn("Safe: Maria, Carlos and Leo", esc["draft_message"])
        
    def test_contact_action_wording_two_unaccounted(self):
        state = self._state_from_statuses({"Maria": "pending", "Carlos": "pending"}, 12)
        esc = build_escalation(self.rivera_plan, state, self.now)
        steps = esc["next_steps"]
        contact_step = next(s for s in steps if s["priority"] == 2)
        self.assertEqual(contact_step["action"], "Contact Uncle Juan and ask them to help check on Carlos and Maria")
        
    def test_singular_and_plural_pet_wording(self):
        # 1 pet pending
        state = self._state_from_statuses({"Buddy": "pending"}, 0)
        esc = build_escalation(self.rivera_plan, state, self.now)
        pet_step = next(s for s in esc["next_steps"] if s["priority"] == 5)
        self.assertEqual(pet_step["action"], "Confirm where Buddy is")
        self.assertIn("Buddy not yet confirmed.", esc["speakable"])
        
        # 2 pets pending
        self.rivera_plan["members"].append({"id": 6, "name": "Rex", "is_pet": 1, "support_level": "dependent"})
        state = self._state_from_statuses({"Buddy": "pending", "Rex": "pending"}, 0)
        esc = build_escalation(self.rivera_plan, state, self.now)
        pet_step = next(s for s in esc["next_steps"] if s["priority"] == 5)
        self.assertEqual(pet_step["action"], "Confirm where Buddy and Rex are")
        self.assertIn("Buddy and Rex not yet confirmed.", esc["speakable"])
        self.rivera_plan["members"].pop()
        
    def test_vulnerable_first_and_capping(self):
        # Carlos (independent) and Elena (vulnerable) both pending
        state = self._state_from_statuses({"Carlos": "pending", "Elena": "pending"}, 0)
        esc = build_escalation(self.rivera_plan, state, self.now)
        steps = esc["next_steps"]
        p1_names = [s["who"] for s in steps if s["priority"] == 1]
        # Elena's step comes before Carlos's
        self.assertEqual(p1_names, ["Elena", "Carlos"])

class TestToolsEndToEnd(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).parent / "test_tools_checkins_db.db"
        if self.db_path.exists():
            self.db_path.unlink()
            
        import rise.db
        rise.db.init_db(self.db_path)
        
        from rise.models import Member
        self.repo = rise.repository.Repository(self.db_path)
        hh = self.repo.create_household("The Rivera Family")
        self.repo.add_member(Member(id=0, household_id=hh.id, name="Maria", age_group="adult", support_level="independent", is_pet=0))
        self.repo.add_member(Member(id=0, household_id=hh.id, name="Carlos", age_group="adult", support_level="independent", is_pet=0))
        self.repo.add_member(Member(id=0, household_id=hh.id, name="Elena", age_group="adult", support_level="needs_assistance", mobility_needs="Uses a cane", medical_needs="High blood pressure medication", is_pet=0))
        self.repo.add_member(Member(id=0, household_id=hh.id, name="Leo", age_group="child", support_level="dependent", is_pet=0))
        self.repo.add_member(Member(id=0, household_id=hh.id, name="Buddy", age_group="pet", support_level="dependent", is_pet=1))
        
        os.environ["RISE_DB_PATH"] = str(self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    @patch("rise.tools._now")
    def test_tools_end_to_end(self, mock_now):
        mock_now.return_value = datetime.fromisoformat("2026-10-05T00:00:00+00:00")
        
        rise.tools.start_checkin("Test")
        rise.tools.record_checkin("Maria", "safe")
        rise.tools.record_checkin("Carlos", "safe")
        rise.tools.record_checkin("Elena", "needs_help", note="fell and cannot stand")
        
        res = rise.tools.get_checkin_status()
        self.assertEqual(res["counts"]["safe"], 2)
        self.assertIn("Elena needs help", res["speakable"])
        
        p0 = res["next_steps"][0]
        self.assertEqual(p0["priority"], 0)
        
        rise.tools.close_checkin()
        
        with self.assertRaisesRegex(rise.tools.ToolError, "No check-in is active"):
            rise.tools.get_checkin_status()

    def test_toolerror_database_error_contains_no_sql(self):
        import sqlite3
        from rise.tools import _convert_error
        
        @_convert_error
        def fail():
            raise sqlite3.IntegrityError("UNIQUE constraint failed: incidents.household_id CHECK")
            
        with self.assertRaises(rise.tools.ToolError) as ctx:
            fail()
            
        msg = str(ctx.exception).lower()
        self.assertNotIn("select", msg)
        self.assertNotIn("insert", msg)
        self.assertNotIn("update", msg)
        self.assertNotIn("sqlite", msg)
        self.assertNotIn("check", msg)

    def test_server_py_descriptions(self):
        path = Path(__file__).parent.parent / "server.py"
        source = path.read_text("utf-8")
        
        self.assertIn("does not contact", source)
        self.assertIn("local emergency number", source)

if __name__ == "__main__":
    unittest.main()
