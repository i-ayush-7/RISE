from dataclasses import dataclass
from typing import Optional

@dataclass
class Household:
    id: Optional[int]
    name: str
    address_note: Optional[str]
    created_at: Optional[str] = None

@dataclass
class Member:
    id: Optional[int]
    household_id: int
    name: str
    age_group: str
    support_level: str
    mobility_needs: Optional[str] = None
    medical_needs: Optional[str] = None
    notes: Optional[str] = None
    is_pet: int = 0

@dataclass
class Contact:
    id: Optional[int]
    household_id: int
    name: str
    relationship: str
    phone: str
    priority: int

@dataclass
class MeetingPoint:
    id: Optional[int]
    household_id: int
    label: str
    description: str
    kind: str
