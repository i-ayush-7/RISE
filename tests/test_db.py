import unittest
import sqlite3
from pathlib import Path
from rise.db import init_db, get_connection
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

    def test_create_household_and_summary(self):
        h = self.repo.create_household("Test Family", "123 Test St")
        self.assertIsNotNone(h.id)
        
        summary = self.repo.get_household_summary(h.id)
        self.assertEqual(summary["name"], "Test Family")
        self.assertEqual(summary["address_note"], "123 Test St")
        self.assertEqual(len(summary["members"]), 0)

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
        
        # Verify member exists
        members = self.repo.list_members(h.id)
        self.assertEqual(len(members), 1)
        
        # Delete household
        self.repo.remove_household(h.id)
        
        # Use raw query to ensure member is gone
        from rise.db import transaction
        with transaction(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM members WHERE household_id = ?", (h.id,))
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 0)

    def test_invalid_support_level(self):
        h = self.repo.create_household("Test Family")
        m = Member(id=None, household_id=h.id, name="John", age_group="adult", support_level="invalid_level")
        
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add_member(m)

if __name__ == "__main__":
    unittest.main()
