import unittest
from pathlib import Path
from rise.db import init_db
from rise.repository import Repository
from mcp.server.mcpserver.exceptions import ToolError
from rise.tools import (
    resolve_household_id, get_household_plan, list_people_needing_help, 
    add_member, update_member, add_contact, update_contact, 
    add_meeting_point, update_meeting_point, list_households, get_repo
)
import os
import rise.tools

class TestTools(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).parent / "test_tools_rise.db"
        if self.db_path.exists():
            self.db_path.unlink()
        
        # Override RISE_DB_PATH for tests
        self.old_env = os.environ.get("RISE_DB_PATH")
        os.environ["RISE_DB_PATH"] = str(self.db_path)
        
        # Ensure it's restored after each test
        def restore_env():
            if self.old_env is None:
                del os.environ["RISE_DB_PATH"]
            else:
                os.environ["RISE_DB_PATH"] = self.old_env
        self.addCleanup(restore_env)
        
        init_db(self.db_path)
        self.repo = get_repo()
        
    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_no_remove_delete_functions(self):
        for name in dir(rise.tools):
            if callable(getattr(rise.tools, name)):
                self.assertFalse(name.startswith("remove"), f"Found function {name} starting with remove")
                self.assertFalse(name.startswith("delete"), f"Found function {name} starting with delete")

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
        self.assertEqual(resolve_household_id(self.repo, 1), 1)

    def test_resolve_household_id_invalid(self):
        self.repo.create_household("Family A")
        with self.assertRaises(ValueError) as ctx:
            resolve_household_id(self.repo, 999)
        self.assertIn("Household not found.", str(ctx.exception))

    def test_resolve_household_id_bool(self):
        self.repo.create_household("Family A")
        with self.assertRaises(ValueError) as ctx:
            resolve_household_id(self.repo, True)
        self.assertIn("household_id must be an integer", str(ctx.exception))

    def test_add_member_invalid_household(self):
        self.repo.create_household("Family A")
        with self.assertRaises(ToolError) as ctx:
            add_member("A", "adult", "independent", household_id=999)
        self.assertIn("Household not found.", str(ctx.exception))

    def test_list_households(self):
        self.repo.create_household("Fam A")
        hh = list_households()
        self.assertEqual(len(hh), 1)
        self.assertEqual(hh[0]["name"], "Fam A")

    def test_get_household_plan_people_pets_need_help(self):
        h = self.repo.create_household("The Rivera Family")
        add_member("A", "adult", "independent")
        add_member("B", "adult", "independent")
        add_member("C", "adult", "needs_assistance")
        add_member("D", "adult", "dependent")
        add_member("Rover", "pet", "dependent")
        plan = get_household_plan()
        self.assertEqual("The Rivera Family has 4 people and 1 pet. 2 people need assistance.", plan["summary"], repr(plan["summary"]))

    def test_get_household_plan_people_pets_one_needs_help(self):
        h = self.repo.create_household("Test Fam")
        add_member("A", "adult", "independent")
        add_member("B", "adult", "needs_assistance")
        add_member("Rover", "pet", "dependent")
        plan = get_household_plan()
        self.assertEqual("Test Fam has 2 people and 1 pet. 1 person needs assistance.", plan["summary"], repr(plan["summary"]))

    def test_get_household_plan_one_person_none_need_help(self):
        h = self.repo.create_household("Test Fam")
        add_member("A", "adult", "independent")
        plan = get_household_plan()
        self.assertEqual("Test Fam has 1 person. Everyone is independent.", plan["summary"], repr(plan["summary"]))

    def test_get_household_plan_plural_people_plural_pets_no_help(self):
        h = self.repo.create_household("Test Fam")
        add_member("A", "adult", "independent")
        add_member("B", "adult", "independent")
        add_member("C", "adult", "independent")
        add_member("Rover", "pet", "dependent")
        add_member("Spot", "pet", "dependent")
        plan = get_household_plan()
        self.assertEqual("Test Fam has 3 people and 2 pets. Everyone is independent.", plan["summary"], repr(plan["summary"]))

    def test_get_household_plan_no_people_plural_pets(self):
        h = self.repo.create_household("Test Fam")
        add_member("Rover", "pet", "dependent")
        add_member("Spot", "pet", "dependent")
        plan = get_household_plan()
        self.assertEqual("Test Fam has 2 pets and no people.", plan["summary"], repr(plan["summary"]))

    def test_get_household_plan_no_members(self):
        h = self.repo.create_household("Test Fam")
        plan = get_household_plan()
        self.assertEqual("Test Fam has no members yet.", plan["summary"], repr(plan["summary"]))

    def test_list_people_needing_help(self):
        h = self.repo.create_household("Test Fam")
        add_member("John", "adult", "independent")
        add_member("Gramps", "senior", "needs_assistance")
        add_member("Jane", "adult", "independent", mobility_needs="crutches")
        add_member("Rover", "pet", "dependent")  # Should be excluded
        
        needs_help = list_people_needing_help()
        self.assertEqual(len(needs_help), 2)
        names = [n["name"] for n in needs_help]
        self.assertIn("Gramps", names)
        self.assertIn("Jane", names)
        self.assertNotIn("Rover", names)
        
    def test_name_too_long(self):
        self.repo.create_household("Fam")
        long_name = "A" * 201
        with self.assertRaises(ToolError) as ctx:
            add_member(long_name, "adult", "independent")
        self.assertIn("must not exceed 200 characters", str(ctx.exception))
        
    def test_notes_too_long(self):
        self.repo.create_household("Fam")
        long_notes = "A" * 1001
        with self.assertRaises(ToolError) as ctx:
            add_member("John", "adult", "independent", notes=long_notes)
        self.assertIn("must not exceed 1000 characters", str(ctx.exception))
        
    def test_mobility_needs_too_long(self):
        self.repo.create_household("Fam")
        long_needs = "A" * 1001
        with self.assertRaises(ToolError) as ctx:
            add_member("John", "adult", "independent", mobility_needs=long_needs)
        self.assertIn("must not exceed 1000 characters", str(ctx.exception))

    def test_bad_phone(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ToolError) as ctx:
            add_contact("Doc", "abcd")
        self.assertIn("invalid characters", str(ctx.exception))
        
    def test_bad_priority_zero(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ToolError) as ctx:
            add_contact("Doc", "555-1234", priority=0)
        self.assertIn("priority must be >= 1", str(ctx.exception))
        
    def test_bad_priority_bool(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ToolError) as ctx:
            add_contact("Doc", "555-1234", priority=True)
        self.assertIn("priority must be an integer", str(ctx.exception))
        
    def test_bad_priority_string(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ToolError) as ctx:
            add_contact("Doc", "555-1234", priority="high")
        self.assertIn("priority must be an integer", str(ctx.exception))
        
    def test_invalid_meeting_point_kind(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ToolError) as ctx:
            add_meeting_point("Park", "secondary")
        self.assertIn("kind must be one of", str(ctx.exception))
        
    def test_pet_age_group_derivation(self):
        self.repo.create_household("Fam")
        m = add_member("Rover", "pet", "dependent")
        self.assertEqual(m["is_pet"], 1)
        m2 = add_member("John", "adult", "independent")
        self.assertEqual(m2["is_pet"], 0)
        
    def test_update_age_group_to_pet_sets_is_pet(self):
        self.repo.create_household("Fam")
        m = add_member("Alien", "adult", "independent")
        self.assertEqual(m["is_pet"], 0)
        update_member(m["id"], age_group="pet")
        plan = get_household_plan()
        self.assertEqual(plan["pets"][0]["id"], m["id"])
        
    def test_update_age_group_away_from_pet_clears_is_pet(self):
        self.repo.create_household("Fam")
        m = add_member("Rover", "pet", "dependent")
        self.assertEqual(m["is_pet"], 1)
        update_member(m["id"], age_group="adult")
        plan = get_household_plan()
        self.assertEqual(len(plan["pets"]), 0)
        
    def test_nothing_to_update(self):
        self.repo.create_household("Fam")
        m = add_member("John", "adult", "independent")
        with self.assertRaises(ToolError) as ctx:
            update_member(m["id"])
        self.assertIn("Nothing to update", str(ctx.exception))

    def test_update_member_lookuperror_translation(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ToolError) as ctx:
            update_member(999, name="Ghost")
        self.assertIn("Record not found", str(ctx.exception))

    def test_scoping_update_member(self):
        h1 = self.repo.create_household("Fam 1")
        h2 = self.repo.create_household("Fam 2")
        m1 = add_member("John", "adult", "independent", household_id=h1.id)
        
        with self.assertRaises(ToolError) as ctx:
            update_member(m1["id"], name="Johnny", household_id=h2.id)
        self.assertIn("Record not found", str(ctx.exception))
        
    def test_scoping_update_contact(self):
        h1 = self.repo.create_household("Fam 1")
        h2 = self.repo.create_household("Fam 2")
        c1 = add_contact("Dr", "555", household_id=h1.id)
        
        with self.assertRaises(ToolError) as ctx:
            update_contact(c1["id"], name="Doctor", household_id=h2.id)
        self.assertIn("Record not found", str(ctx.exception))
        
    def test_scoping_update_meeting_point(self):
        h1 = self.repo.create_household("Fam 1")
        h2 = self.repo.create_household("Fam 2")
        mp1 = add_meeting_point("Park", "primary", household_id=h1.id)
        
        with self.assertRaises(ToolError) as ctx:
            update_meeting_point(mp1["id"], label="Lake", household_id=h2.id)
        self.assertIn("Record not found", str(ctx.exception))

    def test_update_clear_fields(self):
        self.repo.create_household("Fam")
        m = add_member("John", "adult", "independent", mobility_needs="cane")
        c = add_contact("Dr", "555", relationship="Doctor")
        mp = add_meeting_point("Park", "primary", description="Big tree")
        
        update_member(m["id"], mobility_needs="")
        update_contact(c["id"], relationship="")
        update_meeting_point(mp["id"], description="")
        
        plan = get_household_plan()
        mem = next(mem for mem in plan["members"] if mem["id"] == m["id"])
        con = next(con for con in plan["contacts"] if con["id"] == c["id"])
        pt = next(pt for pt in plan["meeting_points"] if pt["id"] == mp["id"])
        
        self.assertIsNone(mem["mobility_needs"])
        self.assertIsNone(con["relationship"])
        self.assertIsNone(pt["description"])
        
    def test_invalid_age_group_msg(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ToolError) as ctx:
            add_member("Ghost", "ghost", "independent")
        self.assertEqual("age_group must be one of: adult, child, pet, senior", str(ctx.exception))

    def test_update_contact_invalid_phone(self):
        self.repo.create_household("Fam")
        c = add_contact("Dr", "555")
        with self.assertRaises(ToolError) as ctx:
            update_contact(c["id"], phone="!@#")
        self.assertEqual("phone contains invalid characters", str(ctx.exception))

    def test_update_contact_priority_zero(self):
        self.repo.create_household("Fam")
        c = add_contact("Dr", "555")
        with self.assertRaises(ToolError) as ctx:
            update_contact(c["id"], priority=0)
        self.assertEqual("priority must be >= 1", str(ctx.exception))

    def test_update_meeting_point_invalid_kind(self):
        self.repo.create_household("Fam")
        mp = add_meeting_point("Park", "primary")
        with self.assertRaises(ToolError) as ctx:
            update_meeting_point(mp["id"], kind="galaxy")
        self.assertEqual("kind must be one of: backup, out_of_area, primary", str(ctx.exception))

    def test_update_member_invalid_support_level(self):
        self.repo.create_household("Fam")
        m = add_member("John", "adult", "independent")
        with self.assertRaises(ToolError) as ctx:
            update_member(m["id"], support_level="superhero")
        self.assertEqual("support_level must be one of: dependent, independent, needs_assistance", str(ctx.exception))

    def test_get_safety_advice_household_not_found(self):
        self.repo.create_household("Fam")
        with self.assertRaises(ToolError) as ctx:
            rise.tools.get_safety_advice(999)
        self.assertEqual("Household not found.", str(ctx.exception))

    def test_error_message_leakage(self):
        from rise.tools import _convert_error
        import sqlite3
        
        @_convert_error
        def fake_db_func():
            raise sqlite3.IntegrityError("CHECK constraint failed: members")
            
        with self.assertLogs("rise.tools", level="ERROR") as log:
            with self.assertRaises(ToolError) as ctx:
                fake_db_func()
                
        self.assertIn("CHECK constraint failed: members", log.output[0])
            
        err = str(ctx.exception).lower()
        for forbidden in ["select", "insert", "update", "sqlite", "check"]:
            self.assertNotIn(forbidden, err)


    def test_checkins_no_active_msg(self):
        from rise.tools import record_checkin, close_checkin, get_checkin_status, ToolError, get_repo
        from rise.checkins import NO_ACTIVE_MSG
        from rise.db import transaction
        # Create a household first so it doesn't fail with "No households exist."
        with transaction(get_repo().db_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO households (name) VALUES ('Test HH')")
        
        expected = "No check-in is active. Use start_checkin to begin one."
        self.assertEqual(NO_ACTIVE_MSG, expected)
        
        with self.assertRaisesRegex(ToolError, f"^{expected}$"):
            record_checkin("Alice", "safe")
            
        with self.assertRaisesRegex(ToolError, f"^{expected}$"):
            close_checkin()
            
        with self.assertRaisesRegex(ToolError, f"^{expected}$"):
            get_checkin_status()

if __name__ == '__main__':
    unittest.main()
