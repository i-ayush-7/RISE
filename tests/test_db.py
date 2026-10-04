import unittest
import sqlite3
from pathlib import Path
from rise.db import init_db, transaction
from rise.repository import Repository
from rise.models import Member, Contact, MeetingPoint

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("tests/test_rise.db")
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)
        self.repo = Repository(self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_create_household(self):
        h = self.repo.create_household("Test Family", "123 Test St")
        self.assertIsNotNone(h.id)
        self.assertEqual(h.name, "Test Family")

    def test_add_members(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="John", age_group="adult", support_level="independent")
        self.repo.add_member(m)
        self.assertIsNotNone(m.id)
        
        members = self.repo.list_members(h.id)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].name, "John")

    def test_cascade_delete(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="John", age_group="adult", support_level="independent")
        self.repo.add_member(m)
        
        c = Contact(id=None, household_id=h.id, name="Doc", relationship="Dr", phone="555", priority=1)
        self.repo.add_contact(c)
        
        mp = MeetingPoint(id=None, household_id=h.id, label="Park", description="Tree", kind="primary")
        self.repo.add_meeting_point(mp)
        
        # Verify they exist
        self.assertEqual(len(self.repo.list_members(h.id)), 1)
        self.assertEqual(len(self.repo.list_contacts(h.id)), 1)
        self.assertEqual(len(self.repo.list_meeting_points(h.id)), 1)
        
        # Delete household
        self.repo.remove_household(h.id)
        
        # Verify cascade
        with transaction(self.db_path) as conn:
            self.assertEqual(len(conn.execute("SELECT * FROM members WHERE household_id = ?", (h.id,)).fetchall()), 0)
            self.assertEqual(len(conn.execute("SELECT * FROM contacts WHERE household_id = ?", (h.id,)).fetchall()), 0)
            self.assertEqual(len(conn.execute("SELECT * FROM meeting_points WHERE household_id = ?", (h.id,)).fetchall()), 0)

    def test_get_household_summary(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="John", age_group="adult", support_level="independent")
        self.repo.add_member(m)
        c = Contact(id=None, household_id=h.id, name="Doc", relationship="Dr", phone="555", priority=1)
        self.repo.add_contact(c)
        mp = MeetingPoint(id=None, household_id=h.id, label="Park", description="Tree", kind="primary")
        self.repo.add_meeting_point(mp)

        summary = self.repo.get_household_summary(h.id)
        self.assertEqual(summary["name"], "Test Family")
        self.assertEqual(len(summary["members"]), 1)
        self.assertEqual(summary["members"][0]["name"], "John")
        self.assertEqual(len(summary["contacts"]), 1)
        self.assertEqual(summary["contacts"][0]["name"], "Doc")
        self.assertEqual(len(summary["meeting_points"]), 1)
        self.assertEqual(summary["meeting_points"][0]["label"], "Park")

    def test_invalid_support_level_rejected(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="John", age_group="adult", support_level="invalid_level")
        
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add_member(m)

    def test_invalid_age_group_rejected(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="John", age_group="immortal", support_level="independent")
        
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add_member(m)

    def test_update_disallowed_column_raises_value_error(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="John", age_group="adult", support_level="independent")
        self.repo.add_member(m)
        
        with self.assertRaises(ValueError):
            self.repo.update_member(m.id, {"id": 9999, "name": "Johnny"})

    def test_update_empty_dict_raises_value_error(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="John", age_group="adult", support_level="independent")
        self.repo.add_member(m)
        
        with self.assertRaises(ValueError):
            self.repo.update_member(m.id, {})
            
    def test_sql_injection_attempt_stored_as_text(self):
        h = self.repo.create_household("Test Family")
        # Attempt SQL injection
        evil_name = "Robert'); DROP TABLE members;--"
        m = Member(id=None, household_id=h.id, name=evil_name, age_group="adult", support_level="independent")
        self.repo.add_member(m)
        
        members = self.repo.list_members(h.id)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].name, evil_name)
        
        # Verify table still exists
        with transaction(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM members").fetchall()
            self.assertEqual(len(rows), 1)

    def test_pet_inconsistent_age_group(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="Buddy", age_group="adult", support_level="independent", is_pet=1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add_member(m)

    def test_pet_inconsistent_is_pet(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="Buddy", age_group="pet", support_level="independent", is_pet=0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add_member(m)

    def test_update_missing_member_raises_lookuperror(self):
        with self.assertRaises(LookupError):
            self.repo.update_member(9999, {"name": "Ghost"})

    def test_remove_missing_member_raises_lookuperror(self):
        with self.assertRaises(LookupError):
            self.repo.remove_member(9999)

if __name__ == "__main__":
    unittest.main()
