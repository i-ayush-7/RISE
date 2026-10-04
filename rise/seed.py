from pathlib import Path
from rise.db import init_db, DEFAULT_DB_PATH
from rise.models import Member, Contact, MeetingPoint
from rise.repository import Repository
import pprint

def seed_data(db_path: Path = DEFAULT_DB_PATH):
    init_db(db_path)
    repo = Repository(db_path)
    
    print("Creating household...")
    household = repo.create_household(
        name="The Rivera Family",
        address_note="123 Fictional Lane, Springfield (Blue house with white trim)"
    )
    
    print(f"Created household with ID: {household.id}")
    
    # 5 Members
    members = [
        Member(id=None, household_id=household.id, name="Maria Rivera", age_group="adult", support_level="independent", notes="Mother, family organizer"),
        Member(id=None, household_id=household.id, name="Carlos Rivera", age_group="adult", support_level="independent", notes="Father"),
        Member(id=None, household_id=household.id, name="Elena Rivera", age_group="senior", support_level="needs_assistance", mobility_needs="Uses a cane, cannot walk long distances", medical_needs="High blood pressure medication"),
        Member(id=None, household_id=household.id, name="Leo Rivera", age_group="child", support_level="dependent", notes="6 years old"),
        Member(id=None, household_id=household.id, name="Buddy", age_group="pet", support_level="dependent", is_pet=1, notes="Golden Retriever, very friendly")
    ]
    
    for m in members:
        repo.add_member(m)
        
    # 2 Contacts
    contacts = [
        Contact(id=None, household_id=household.id, name="Dr. Sarah Jenkins", relationship="Family Doctor", phone="555-0100", priority=2),
        Contact(id=None, household_id=household.id, name="Uncle Juan", relationship="Uncle (Out of state)", phone="555-0199", priority=1)
    ]
    
    for c in contacts:
        repo.add_contact(c)
        
    # 2 Meeting Points
    points = [
        MeetingPoint(id=None, household_id=household.id, label="Neighborhood Park", description="Oak Tree in the center of the park", kind="primary"),
        MeetingPoint(id=None, household_id=household.id, label="Springfield Community Center", description="Main entrance desk", kind="out_of_area")
    ]
    
    for p in points:
        repo.add_meeting_point(p)
        
    print("\nHousehold Summary:")
    summary = repo.get_household_summary(household.id)
    pprint.pprint(summary)

if __name__ == "__main__":
    seed_data()
