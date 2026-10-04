import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from rise.repository import Repository
from rise.models import Member, Contact, MeetingPoint
from rise.db import get_connection

def get_repo() -> Repository:
    from rise.db import DEFAULT_DB_PATH, PROJECT_ROOT
    path = Path(os.environ.get("RISE_DB_PATH", PROJECT_ROOT / "data" / "rise.db"))
    return Repository(path)

def _convert_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database constraint violation. Please check your inputs.")
        except LookupError as e:
            raise ValueError(f"Record not found.")
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
    if not s and not required:
        return None
    if not s:
        raise ValueError(f"{name} must be a non-empty string")
    if not isinstance(s, str):
        raise ValueError(f"{name} must be a string")
    if len(s) > max_length:
        raise ValueError(f"{name} must not exceed {max_length} characters")
    return s

def validate_enum(val: Any, name: str, allowed: set) -> str:
    if val not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return val

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
        
    members = summary_data.get('members', [])
    pets = [m for m in members if m['is_pet'] == 1]
    needs_help = [m for m in members if m['support_level'] != 'independent' or m['mobility_needs'] or m['medical_needs']]
    
    name = summary_data.get('name', 'Unknown')
    member_count = len(members)
    pet_count = len(pets)
    help_count = len(needs_help)
    
    pet_str = f" including {pet_count} pet{'s' if pet_count != 1 else ''}" if pet_count > 0 else ""
    help_str = f" {help_count} person{'s' if help_count != 1 else ''} needs assistance." if help_count > 0 else " Everyone is independent."
    
    summary_str = f"{name}: {member_count} members{pet_str}.{help_str}"
    
    summary_data['summary'] = summary_str
    return summary_data

@_convert_error
def list_people_needing_help(household_id: Optional[int] = None) -> List[Dict[str, Any]]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    members = repo.list_members(hid)
    
    needs_help = []
    for m in members:
        if m.support_level != 'independent' or m.mobility_needs or m.medical_needs:
            needs_help.append(m.__dict__)
            
    return needs_help

@_convert_error
def add_member(name: str, age_group: str, support_level: str, 
               mobility_needs: Optional[str] = None, medical_needs: Optional[str] = None, 
               notes: Optional[str] = None, is_pet: int = 0, 
               household_id: Optional[int] = None) -> Dict[str, Any]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    
    name = validate_string(name, "name")
    age_group = validate_enum(age_group, "age_group", {'child', 'adult', 'senior', 'pet'})
    support_level = validate_enum(support_level, "support_level", {'independent', 'needs_assistance', 'dependent'})
    notes = validate_string(notes, "notes", 1000, False)
    
    m = Member(id=None, household_id=hid, name=name, age_group=age_group, 
               support_level=support_level, mobility_needs=mobility_needs, 
               medical_needs=medical_needs, notes=notes, is_pet=is_pet)
    
    added = repo.add_member(m)
    return added.__dict__

@_convert_error
def update_member(member_id: int, updates: Dict[str, Any], household_id: Optional[int] = None) -> Dict[str, str]:
    repo = get_repo()
    if 'name' in updates:
        updates['name'] = validate_string(updates['name'], "name")
    if 'notes' in updates:
        updates['notes'] = validate_string(updates['notes'], "notes", 1000, False)
    if 'age_group' in updates:
        updates['age_group'] = validate_enum(updates['age_group'], "age_group", {'child', 'adult', 'senior', 'pet'})
    if 'support_level' in updates:
        updates['support_level'] = validate_enum(updates['support_level'], "support_level", {'independent', 'needs_assistance', 'dependent'})
        
    repo.update_member(member_id, updates)
    return {"status": "success"}

@_convert_error
def add_contact(name: str, phone: str, relationship: Optional[str] = None, priority: int = 1, household_id: Optional[int] = None) -> Dict[str, Any]:
    repo = get_repo()
    hid = resolve_household_id(repo, household_id)
    
    name = validate_string(name, "name")
    
    c = Contact(id=None, household_id=hid, name=name, relationship=relationship, phone=phone, priority=priority)
    added = repo.add_contact(c)
    return added.__dict__

@_convert_error
def update_contact(contact_id: int, updates: Dict[str, Any], household_id: Optional[int] = None) -> Dict[str, str]:
    repo = get_repo()
    if 'name' in updates:
        updates['name'] = validate_string(updates['name'], "name")
    repo.update_contact(contact_id, updates)
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
def update_meeting_point(mp_id: int, updates: Dict[str, Any], household_id: Optional[int] = None) -> Dict[str, str]:
    repo = get_repo()
    if 'label' in updates:
        updates['label'] = validate_string(updates['label'], "label")
    if 'description' in updates:
        updates['description'] = validate_string(updates['description'], "description", 1000, False)
    if 'kind' in updates:
        updates['kind'] = validate_enum(updates['kind'], "kind", {'primary', 'backup', 'out_of_area'})
        
    repo.update_meeting_point(mp_id, updates)
    return {"status": "success"}
