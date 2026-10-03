import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from rise.models import Household, Member, Contact, MeetingPoint
from rise.db import get_connection, transaction, DEFAULT_DB_PATH

class Repository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def create_household(self, name: str, address_note: Optional[str] = None) -> Household:
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO households (name, address_note) VALUES (?, ?)",
                (name, address_note)
            )
            household_id = cursor.lastrowid
            
            cursor = conn.execute("SELECT * FROM households WHERE id = ?", (household_id,))
            row = cursor.fetchone()
            return Household(**dict(row))

    def add_member(self, member: Member) -> Member:
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO members (household_id, name, age_group, support_level, 
                                        mobility_needs, medical_needs, notes, is_pet) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (member.household_id, member.name, member.age_group, member.support_level,
                 member.mobility_needs, member.medical_needs, member.notes, member.is_pet)
            )
            member.id = cursor.lastrowid
            return member

    def list_members(self, household_id: int) -> List[Member]:
        with transaction(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM members WHERE household_id = ?", (household_id,))
            return [Member(**dict(row)) for row in cursor.fetchall()]

    def update_member(self, member: Member) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                """UPDATE members 
                   SET name = ?, age_group = ?, support_level = ?, mobility_needs = ?, 
                       medical_needs = ?, notes = ?, is_pet = ?
                   WHERE id = ?""",
                (member.name, member.age_group, member.support_level, member.mobility_needs,
                 member.medical_needs, member.notes, member.is_pet, member.id)
            )

    def remove_member(self, member_id: int) -> None:
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM members WHERE id = ?", (member_id,))

    def add_contact(self, contact: Contact) -> Contact:
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO contacts (household_id, name, relationship, phone, priority) VALUES (?, ?, ?, ?, ?)",
                (contact.household_id, contact.name, contact.relationship, contact.phone, contact.priority)
            )
            contact.id = cursor.lastrowid
            return contact
            
    def list_contacts(self, household_id: int) -> List[Contact]:
        with transaction(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM contacts WHERE household_id = ?", (household_id,))
            return [Contact(**dict(row)) for row in cursor.fetchall()]

    def update_contact(self, contact: Contact) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                """UPDATE contacts 
                   SET name = ?, relationship = ?, phone = ?, priority = ?
                   WHERE id = ?""",
                (contact.name, contact.relationship, contact.phone, contact.priority, contact.id)
            )

    def remove_contact(self, contact_id: int) -> None:
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))

    def add_meeting_point(self, mp: MeetingPoint) -> MeetingPoint:
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO meeting_points (household_id, label, description, kind) VALUES (?, ?, ?, ?)",
                (mp.household_id, mp.label, mp.description, mp.kind)
            )
            mp.id = cursor.lastrowid
            return mp

    def list_meeting_points(self, household_id: int) -> List[MeetingPoint]:
        with transaction(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM meeting_points WHERE household_id = ?", (household_id,))
            return [MeetingPoint(**dict(row)) for row in cursor.fetchall()]

    def update_meeting_point(self, mp: MeetingPoint) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                """UPDATE meeting_points 
                   SET label = ?, description = ?, kind = ?
                   WHERE id = ?""",
                (mp.label, mp.description, mp.kind, mp.id)
            )

    def remove_meeting_point(self, mp_id: int) -> None:
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM meeting_points WHERE id = ?", (mp_id,))

    def remove_household(self, household_id: int) -> None:
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM households WHERE id = ?", (household_id,))

    def get_household_summary(self, household_id: int) -> Dict[str, Any]:
        with transaction(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM households WHERE id = ?", (household_id,))
            household_row = cursor.fetchone()
            if not household_row:
                return {}
            
            summary = dict(household_row)
            
            cursor = conn.execute("SELECT * FROM members WHERE household_id = ?", (household_id,))
            summary['members'] = [dict(row) for row in cursor.fetchall()]
            
            cursor = conn.execute("SELECT * FROM contacts WHERE household_id = ?", (household_id,))
            summary['contacts'] = [dict(row) for row in cursor.fetchall()]
            
            cursor = conn.execute("SELECT * FROM meeting_points WHERE household_id = ?", (household_id,))
            summary['meeting_points'] = [dict(row) for row in cursor.fetchall()]
            
            return summary
