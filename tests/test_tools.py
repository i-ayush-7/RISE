import unittest
from pathlib import Path
from rise.db import init_db
from rise.repository import Repository
from rise.tools import (
    resolve_household_id, get_household_plan, list_people_needing_help, 
    add_member, update_member, add_contact, update_contact, 
    add_meeting_point, update_meeting_point, list_households, get_repo
)
import os

class TestTools(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("tests/test_tools_rise.db")
        if self.db_path.exists():
            self.db_path.unlink()
        
        # Override RISE_DB_PATH for tests
        os.environ["RISE_DB_PATH"] = str(self.db_path)
        init_db(self.db_path)
        self.repo = get_repo()
        
    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_resolve_household_id_zero(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_household_id(self.repo, None)
        self.assertIn("No households exist.", str(ctx.exception))
        
    def test_resolve_household_id_one(self):
        h = self.repo.create_household("Solo Family")
        self.assertEqual(resolve_household_id(self.repo, None), h.id)
        
    def test_resolve_household_id_multiple(self):
        self.repo.create_household("Family A")
        self.repo.create_household("Family B")
        with self.assertRaises(ValueError) as ctx:
            resolve_household_id(self.repo, None)
        self.assertIn("Multiple households exist.", str(ctx.exception))
        
    def test_resolve_household_id_explicit(self):
        self.repo.create_household("Family A")
        self.assertEqual(resolve_household_id(self.repo, 999), 999)

    def test_list_households(self):
        self.repo.create_household("Fam A")
        hh = list_households()
        self.assertEqual(len(hh), 1)
        self.assertEqual(hh[0]["name"], "Fam A")

    def test_get_household_plan(self):
        h = self.repo.create_household("Test Fam")
        add_member("John", "adult", "independent")
        add_member("Rover", "pet", "dependent", is_pet=1)
        add_member("Gramps", "senior", "needs_assistance")
        
        plan = get_household_plan()
        self.assertIn("Test Fam: 3 members including 1 pet. 2 persons needs assistance.", plan["summary"])
        
    def test_get_household_plan_no_help_needed(self):
        h = self.repo.create_household("Test Fam")
        add_member("John", "adult", "independent")
        plan = get_household_plan()
        self.assertIn("Everyone is independent.", plan["summary"])

    def test_list_people_needing_help(self):
        h = self.repo.create_household("Test Fam")
        add_member("John", "adult", "independent")
        add_member("Gramps", "senior", "needs_assistance")
        add_member("Jane", "adult", "independent", mobility_needs="crutches")
        
        needs_help = list_people_needing_help()
        self.assertEqual(len(needs_help), 2)
        
    def test_validation_empty_string(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ValueError) as ctx:
            add_member("", "adult", "independent")
        self.assertIn("name must be a non-empty string", str(ctx.exception))
        
    def test_validation_enum(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ValueError) as ctx:
            add_member("John", "alien", "independent")
        self.assertIn("age_group must be one of", str(ctx.exception))

    def test_update_member_lookuperror_translation(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ValueError) as ctx:
            update_member(999, {"name": "Ghost"})
        self.assertIn("Record not found", str(ctx.exception))

    def test_add_contact_and_update(self):
        self.repo.create_household("Fam")
        c = add_contact("Dr", "555-0100")
        self.assertEqual(c["name"], "Dr")
        
        update_contact(c["id"], {"priority": 2})
        plan = get_household_plan()
        self.assertEqual(plan["contacts"][0]["priority"], 2)

    def test_add_meeting_point_and_update(self):
        self.repo.create_household("Fam")
        mp = add_meeting_point("Park", "primary")
        self.assertEqual(mp["label"], "Park")
        
        update_meeting_point(mp["id"], {"kind": "backup"})
        plan = get_household_plan()
        self.assertEqual(plan["meeting_points"][0]["kind"], "backup")

if __name__ == "__main__":
    unittest.main()
