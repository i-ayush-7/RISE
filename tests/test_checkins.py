import unittest
import os
from pathlib import Path
from datetime import datetime
import sqlite3

from rise.db import init_db, transaction
from rise.repository import Repository
from rise.models import Member
from rise.checkins import (
    start_incident, record_checkin, get_incident_state, close_incident, resolve_member_name
)

class TestCheckinsDataLayer(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).parent / "test_checkins_db.db"
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)
        self.repo = Repository(self.db_path)
        self.hh = self.repo.create_household("Test Fam")
        
        self.now = datetime.fromisoformat("2026-10-05T00:00:00+00:00")

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_migration(self):
        with transaction(self.db_path) as conn:
            conn.execute("DROP TABLE checkins")
            conn.execute("DROP TABLE incidents")
            
        init_db(self.db_path)
        with transaction(self.db_path) as conn:
            # Should not raise
            conn.execute("SELECT * FROM incidents").fetchall()
            conn.execute("SELECT * FROM checkins").fetchall()

    def test_start_creates_pending_rows_including_pets(self):
        m1 = self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice Smith", age_group="adult", support_level="independent", is_pet=0))
        m2 = self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Doggo", age_group="pet", support_level="dependent", is_pet=1))
        
        start_incident(self.db_path, self.hh.id, "Reason", self.now)
        state = get_incident_state(self.db_path, self.hh.id)
        
        self.assertEqual(len(state["members"]), 2)
        self.assertEqual(state["members"][0]["status"], "pending")
        self.assertEqual(state["members"][1]["status"], "pending")

    def test_second_start_raises_error(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice Smith", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "Reason", self.now)
        with self.assertRaisesRegex(ValueError, "A check-in is already active for this household. Use get_checkin_status or close_checkin."):
            start_incident(self.db_path, self.hh.id, "Reason 2", self.now)

    def test_start_no_members_raises_error(self):
        with self.assertRaisesRegex(ValueError, "Add household members before starting a check-in."):
            start_incident(self.db_path, self.hh.id, "Reason", self.now)

    def test_start_after_close_works(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice Smith", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "Reason", self.now)
        close_incident(self.db_path, self.hh.id, self.now)
        start_incident(self.db_path, self.hh.id, "Reason 2", self.now)
        state = get_incident_state(self.db_path, self.hh.id)
        self.assertEqual(state["reason"], "Reason 2")

    def test_direct_insert_second_active_incident_raises_integrity_error(self):
        with transaction(self.db_path) as conn:
            conn.execute("INSERT INTO incidents (household_id, started_at, status, reason) VALUES (?, ?, 'active', ?)", (self.hh.id, self.now.isoformat(), "R1"))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO incidents (household_id, started_at, status, reason) VALUES (?, ?, 'active', ?)", (self.hh.id, self.now.isoformat(), "R2"))

    def test_record_by_full_name(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice Smith", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "R", self.now)
        record_checkin(self.db_path, self.hh.id, "alice smith", "safe", None, self.now)
        state = get_incident_state(self.db_path, self.hh.id)
        self.assertEqual(state["members"][0]["status"], "safe")

    def test_record_by_unique_first_name(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice Smith", age_group="adult", support_level="independent", is_pet=0))
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Bob Jones", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "R", self.now)
        record_checkin(self.db_path, self.hh.id, "alice", "safe", None, self.now)
        state = get_incident_state(self.db_path, self.hh.id)
        self.assertEqual(state["members"][0]["status"], "safe")

    def test_resolve_member_name_logic(self):
        members = [
            {"id": 1, "name": "Alice Smith"},
            {"id": 2, "name": "Alice Jones"},
            {"id": 3, "name": "Bob Brown"}
        ]
        
        # full name
        res = resolve_member_name(members, "Alice Smith")
        self.assertEqual(res["id"], 1)
        
        # unique first token
        res = resolve_member_name(members, "bob")
        self.assertEqual(res["id"], 3)
        
        # ambiguous
        with self.assertRaisesRegex(ValueError, "Ambiguous name 'alice'. Did you mean: Alice Smith, Alice Jones?"):
            resolve_member_name(members, "alice")
            
        # not found
        with self.assertRaisesRegex(ValueError, "No household member matches that name. Members: Alice Smith, Alice Jones, Bob Brown"):
            resolve_member_name(members, "charlie")

    def test_invalid_status(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "R", self.now)
        with self.assertRaisesRegex(ValueError, "Status must be one of: needs_help, not_responding, pending, safe"):
            record_checkin(self.db_path, self.hh.id, "Alice", "invalid", None, self.now)

    def test_note_over_300_and_control_chars(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "R", self.now)
        
        long_note = "A" * 400
        dirty_note = "Hello\x00World" + long_note
        
        record_checkin(self.db_path, self.hh.id, "Alice", "safe", dirty_note, self.now)
        state = get_incident_state(self.db_path, self.hh.id)
        saved_note = state["members"][0]["note"]
        self.assertEqual(len(saved_note), 300)
        self.assertEqual(saved_note[:10], "HelloWorld")

    def test_no_active_incident_error(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice", age_group="adult", support_level="independent", is_pet=0))
        with self.assertRaisesRegex(ValueError, "No check-in is active. Use start_checkin to begin one."):
            record_checkin(self.db_path, self.hh.id, "Alice", "safe", None, self.now)

    def test_record_after_close_error(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "R", self.now)
        close_incident(self.db_path, self.hh.id, self.now)
        with self.assertRaisesRegex(ValueError, "No check-in is active. Use start_checkin to begin one."):
            record_checkin(self.db_path, self.hh.id, "Alice", "safe", None, self.now)

    def test_correcting_safe_to_needs_help(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "R", self.now)
        record_checkin(self.db_path, self.hh.id, "Alice", "safe", None, self.now)
        record_checkin(self.db_path, self.hh.id, "Alice", "needs_help", None, self.now)
        state = get_incident_state(self.db_path, self.hh.id)
        self.assertEqual(state["members"][0]["status"], "needs_help")

    def test_member_added_after_start_appears_pending(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "R", self.now)
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Bob", age_group="adult", support_level="independent", is_pet=0))
        state = get_incident_state(self.db_path, self.hh.id)
        
        self.assertEqual(len(state["members"]), 2)
        self.assertEqual(state["members"][1]["name"], "Bob")
        self.assertEqual(state["members"][1]["status"], "pending")

    def test_deleting_household_cascades(self):
        self.repo.add_member(Member(id=0, household_id=self.hh.id, name="Alice", age_group="adult", support_level="independent", is_pet=0))
        start_incident(self.db_path, self.hh.id, "R", self.now)
        
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM households WHERE id = ?", (self.hh.id,))
            
            incs = conn.execute("SELECT * FROM incidents").fetchall()
            self.assertEqual(len(incs), 0)
            
            chks = conn.execute("SELECT * FROM checkins").fetchall()
            self.assertEqual(len(chks), 0)

if __name__ == "__main__":
    unittest.main()
