import sqlite3
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from rise.repository import Repository
from rise.models import Member, Contact, MeetingPoint

def get_repo() -> Repository:
    from rise.db import DEFAULT_DB_PATH, PROJECT_ROOT
    path = Path(os.environ.get("RISE_DB_PATH", PROJECT_ROOT / "data" / "rise.db"))
    return Repository(path)

def _convert_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError:
            raise
        except LookupError:
            raise ValueError("Record not found.")
        except sqlite3.Error as e:
            logging.getLogger(__name__).error("Database error: %s", str(e), exc_info=True)
            raise ValueError("A database error occurred while processing your request.")
        except Exception as e:
            logging.getLogger(__name__).error("Unexpected error: %s", str(e), exc_info=True)
            raise ValueError("An unexpected error occurred.")
    return wrapper

def resolve_household_id(repo: Repository, household_id: Optional[int]) -> int:
    from rise.db import transaction
    with transaction(repo.db_path) as conn:
        cursor = conn.execute("SELECT id, name FROM households")
        households = cursor.fetchall()
        
    if household_id is not None:
        return household_id
        
    if len(households) == 1:
        return households[0]['id']
        
    if len(households) == 0:
        raise ValueError("No households exist.")
        
    options = ", ".join([f"{h['id']} ({h['name']})" for h in households])
    raise ValueError(f"Multiple households exist. Please specify household_id. Options: {options}")

def validate_string(s: Any, name: str, max_length: int = 200, required: bool = True) -> Optional[str]:
    if s == "":
        if required:
            raise ValueError(f"{name} must be a non-empty string")
        return None
    if s is None:
        if required:
            raise ValueError(f"{name} must be provided")
        return None
    if not isinstance(s, str):
        raise ValueError(f"{name} must be a string")
    if len(s) > max_length:
        raise ValueError(f"{name} must not exceed {max_length} characters")
    return s

def validate_enum(val: Any, name: str, allowed: set) -> str:
    if val not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return val
    
def validate_phone(phone: Any) -> str:
    if not isinstance(phone, str) or not phone:
        raise ValueError("phone must be a non-empty string")
    if len(phone) > 40:
        raise ValueError("phone must not exceed 40 characters")
    if not all(c.isdigit() or c in " +-()." for c in phone):
        raise ValueError("phone contains invalid characters")
    return phone

def validate_priority(priority: Any) -> int:
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError("priority must be an integer")
    if priority < 1:
        raise ValueError("priority must be >= 1")
    return priority

def validate_id(id_val: Any, name: str) -> int:
    if isinstance(id_val, bool) or not isinstance(id_val, int):
        raise ValueError(f"{name} must be an integer")
    return id_val

@_convert_error
def list_households() -> List[Dict[str, Any]]:
    repo = get_repo()
    from rise.db import transaction
    with transaction(repo.db_path) as conn:
        cursor = conn.execute("SELECT id, name, address_note FROM households")
        return [dict(row) for row in cursor.fetchall()]

@_convert_error
def get_household_plan(household_id: Optional[int] = None) -> Dict[str, Any]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    summary_data = repo.get_household_summary(hid)
    
    if not summary_data:
        raise ValueError("Household not found.")
        
    all_members = summary_data.get('members', [])
    people = [m for m in all_members if m['is_pet'] == 0]
    pets = [m for m in all_members if m['is_pet'] == 1]
    needs_help = [m for m in people if m['support_level'] != 'independent' or m['mobility_needs'] or m['medical_needs']]
    
    name = summary_data.get('name', 'Unknown')
    mem_count = len(people)
    pet_count = len(pets)
    help_count = len(needs_help)
    
    mem_word = "member" if mem_count == 1 else "members"
    pet_word = "pet" if pet_count == 1 else "pets"
    help_word = "person needs" if help_count == 1 else "people need"
    
    pet_str = f" including {pet_count} {pet_word}" if pet_count > 0 else ""
    help_str = f" {help_count} {help_word} assistance." if help_count > 0 else " Everyone is independent."
    
    summary_str = f"{name}: {mem_count} {mem_word}{pet_str}.{help_str}"
    
    summary_data['summary'] = summary_str
    summary_data['pets'] = pets
    return summary_data

@_convert_error
def list_people_needing_help(household_id: Optional[int] = None) -> List[Dict[str, Any]]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    members = repo.list_members(hid)
    
    needs_help = []
    for m in members:
        if m.is_pet == 0 and (m.support_level != 'independent' or m.mobility_needs or m.medical_needs):
            needs_help.append(m.__dict__)
            
    return needs_help

@_convert_error
def add_member(name: str, age_group: str, support_level: str, 
               mobility_needs: Optional[str] = None, medical_needs: Optional[str] = None, 
               notes: Optional[str] = None, household_id: Optional[int] = None) -> Dict[str, Any]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    
    name = validate_string(name, "name")
    age_group = validate_enum(age_group, "age_group", {'child', 'adult', 'senior', 'pet'})
    support_level = validate_enum(support_level, "support_level", {'independent', 'needs_assistance', 'dependent'})
    notes = validate_string(notes, "notes", 1000, False)
    mobility_needs = validate_string(mobility_needs, "mobility_needs", 1000, False)
    medical_needs = validate_string(medical_needs, "medical_needs", 1000, False)
    is_pet = 1 if age_group == 'pet' else 0
    
    m = Member(id=None, household_id=hid, name=name, age_group=age_group, 
               support_level=support_level, mobility_needs=mobility_needs, 
               medical_needs=medical_needs, notes=notes, is_pet=is_pet)
    
    added = repo.add_member(m)
    return added.__dict__

@_convert_error
def update_member(member_id: int, name: Optional[str] = None, age_group: Optional[str] = None, 
                  support_level: Optional[str] = None, mobility_needs: Optional[str] = None, 
                  medical_needs: Optional[str] = None, notes: Optional[str] = None, 
                  household_id: Optional[int] = None) -> Dict[str, str]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    member_id = validate_id(member_id, "member_id")
    
    updates = {}
    if name is not None:
        updates['name'] = validate_string(name, "name")
    if age_group is not None:
        updates['age_group'] = validate_enum(age_group, "age_group", {'child', 'adult', 'senior', 'pet'})
        updates['is_pet'] = 1 if updates['age_group'] == 'pet' else 0
    if support_level is not None:
        updates['support_level'] = validate_enum(support_level, "support_level", {'independent', 'needs_assistance', 'dependent'})
    if mobility_needs is not None:
        updates['mobility_needs'] = validate_string(mobility_needs, "mobility_needs", 1000, False)
    if medical_needs is not None:
        updates['medical_needs'] = validate_string(medical_needs, "medical_needs", 1000, False)
    if notes is not None:
        updates['notes'] = validate_string(notes, "notes", 1000, False)
        
    if not updates:
        raise ValueError("Nothing to update")
        
    repo.update_member(member_id, hid, updates)
    return {"status": "success"}

@_convert_error
def add_contact(name: str, phone: str, relationship: Optional[str] = None, priority: int = 1, household_id: Optional[int] = None) -> Dict[str, Any]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    
    name = validate_string(name, "name")
    phone = validate_phone(phone)
    relationship = validate_string(relationship, "relationship", 200, False)
    priority = validate_priority(priority)
    
    c = Contact(id=None, household_id=hid, name=name, relationship=relationship, phone=phone, priority=priority)
    added = repo.add_contact(c)
    return added.__dict__

@_convert_error
def update_contact(contact_id: int, name: Optional[str] = None, phone: Optional[str] = None, 
                   relationship: Optional[str] = None, priority: Optional[int] = None, 
                   household_id: Optional[int] = None) -> Dict[str, str]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    contact_id = validate_id(contact_id, "contact_id")
    
    updates = {}
    if name is not None:
        updates['name'] = validate_string(name, "name")
    if phone is not None:
        updates['phone'] = validate_phone(phone)
    if relationship is not None:
        updates['relationship'] = validate_string(relationship, "relationship", 200, False)
    if priority is not None:
        updates['priority'] = validate_priority(priority)
        
    if not updates:
        raise ValueError("Nothing to update")
        
    repo.update_contact(contact_id, hid, updates)
    return {"status": "success"}

@_convert_error
def add_meeting_point(label: str, kind: str, description: Optional[str] = None, household_id: Optional[int] = None) -> Dict[str, Any]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    
    label = validate_string(label, "label")
    kind = validate_enum(kind, "kind", {'primary', 'backup', 'out_of_area'})
    description = validate_string(description, "description", 1000, False)
    
    mp = MeetingPoint(id=None, household_id=hid, label=label, description=description, kind=kind)
    added = repo.add_meeting_point(mp)
    return added.__dict__

@_convert_error
def update_meeting_point(mp_id: int, label: Optional[str] = None, kind: Optional[str] = None, 
                         description: Optional[str] = None, household_id: Optional[int] = None) -> Dict[str, str]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    mp_id = validate_id(mp_id, "mp_id")
    
    updates = {}
    if label is not None:
        updates['label'] = validate_string(label, "label")
    if kind is not None:
        updates['kind'] = validate_enum(kind, "kind", {'primary', 'backup', 'out_of_area'})
    if description is not None:
        updates['description'] = validate_string(description, "description", 1000, False)
        
    if not updates:
        raise ValueError("Nothing to update")
        
    repo.update_meeting_point(mp_id, hid, updates)
    return {"status": "success"}
