import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from rise.db import transaction, get_connection

def resolve_member_name(members: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    query_lower = query.lower().strip()
    
    # Exact full name match
    for m in members:
        if m["name"].lower() == query_lower:
            return m
            
    # Unique first name match
    query_first = query_lower.split()[0]
    matches = []
    for m in members:
        if m["name"].lower().split()[0] == query_first:
            matches.append(m)
            
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        names = ", ".join(m["name"] for m in matches)
        raise ValueError(f"Ambiguous name '{query}'. Did you mean: {names}?")
    else:
        names = ", ".join(m["name"] for m in members)
        raise ValueError(f"No household member matches that name. Members: {names}")

def start_incident(db_path: Path, household_id: int, reason: Optional[str], now: datetime):
    if reason:
        reason = "".join(c for c in reason if c.isprintable())[:200]
        
    with transaction(db_path) as conn:
        members = conn.execute("SELECT id FROM members WHERE household_id = ?", (household_id,)).fetchall()
        if not members:
            raise ValueError("Add household members before starting a check-in.")
            
        try:
            cur = conn.execute(
                "INSERT INTO incidents (household_id, started_at, status, reason) VALUES (?, ?, 'active', ?)",
                (household_id, now.isoformat(), reason)
            )
            incident_id = cur.lastrowid
        except sqlite3.IntegrityError as e:
            if "idx_one_active_incident" in str(e) or "UNIQUE constraint failed" in str(e):
                raise ValueError("A check-in is already active for this household. Use get_checkin_status or close_checkin.")
            raise
            
        for m in members:
            conn.execute(
                "INSERT INTO checkins (incident_id, member_id, status, updated_at) VALUES (?, ?, 'pending', ?)",
                (incident_id, m["id"], now.isoformat())
            )

def record_checkin(db_path: Path, household_id: int, member_query: str, status: str, note: Optional[str], now: datetime):
    valid_statuses = ['needs_help', 'not_responding', 'pending', 'safe']
    if status not in valid_statuses:
        raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        
    if note:
        note = "".join(c for c in note if c.isprintable())[:300]
        
    with transaction(db_path) as conn:
        inc = conn.execute("SELECT id FROM incidents WHERE household_id = ? AND status = 'active'", (household_id,)).fetchone()
        if not inc:
            raise ValueError("No check-in is active. Use start_checkin to begin one.")
            
        incident_id = inc["id"]
        members = [dict(m) for m in conn.execute("SELECT * FROM members WHERE household_id = ?", (household_id,)).fetchall()]
        
        member = resolve_member_name(members, member_query)
        member_id = member["id"]
        
        conn.execute("""
            INSERT INTO checkins (incident_id, member_id, status, note, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(incident_id, member_id) DO UPDATE SET
                status = excluded.status,
                note = excluded.note,
                updated_at = excluded.updated_at
        """, (incident_id, member_id, status, note, now.isoformat()))

def get_incident_state(db_path: Path, household_id: int) -> Optional[Dict[str, Any]]:
    with transaction(db_path) as conn:
        inc = conn.execute("SELECT * FROM incidents WHERE household_id = ? AND status = 'active'", (household_id,)).fetchone()
        if not inc:
            return None
            
        members = conn.execute("""
            SELECT m.id as member_id, m.name, m.is_pet, c.status, c.note, c.updated_at
            FROM members m
            LEFT JOIN checkins c ON m.id = c.member_id AND c.incident_id = ?
            WHERE m.household_id = ?
            ORDER BY m.id
        """, (inc["id"], household_id)).fetchall()
        
        member_list = []
        for m in members:
            member_list.append({
                "member_id": m["member_id"],
                "name": m["name"],
                "is_pet": m["is_pet"],
                "status": m["status"] if m["status"] else "pending",
                "note": m["note"],
                "updated_at": m["updated_at"]
            })
            
        return {
            "incident_id": inc["id"],
            "started_at": inc["started_at"],
            "reason": inc["reason"],
            "status": inc["status"],
            "members": member_list
        }

def close_incident(db_path: Path, household_id: int, now: datetime):
    with transaction(db_path) as conn:
        cur = conn.execute("UPDATE incidents SET status = 'closed', closed_at = ? WHERE household_id = ? AND status = 'active'", (now.isoformat(), household_id))
        if cur.rowcount == 0:
            raise ValueError("No check-in is active.")
