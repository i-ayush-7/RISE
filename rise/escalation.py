from typing import Dict, Any, List
from datetime import datetime, timezone

ESCALATION_MINUTES = (5, 10, 20)
DISCLAIMER = "R.I.S.E. does not contact anyone. Use your phone to call or message. If anyone is in immediate danger, call your local emergency number."

def build_escalation(plan: Dict[str, Any], state: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError("now must be timezone-aware")

    members_plan = plan.get("members", [])
    members_state = state.get("members", []) if state else []
    
    plan_by_id = {m.get("id"): m for m in members_plan if "id" in m}
    
    counts = {"safe": 0, "needs_help": 0, "pending": 0, "not_responding": 0, "total": len(members_state)}
    all_accounted_for = True if members_state else False
    
    for m in members_state:
        status = m.get("status", "pending")
        if status in counts:
            counts[status] += 1
        if status != "safe":
            all_accounted_for = False
            
    started_at_str = state.get("started_at") if state else now.isoformat()
    started_at = datetime.fromisoformat(started_at_str)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
        
    elapsed_td = now - started_at
    elapsed_minutes = max(0, int(elapsed_td.total_seconds() // 60))
    
    people_state = [m for m in members_state if not m.get("is_pet")]
    pets_state = [m for m in members_state if m.get("is_pet")]
    
    unaccounted_people = [m for m in people_state if m.get("status") in ("pending", "not_responding")]
    needs_help_people = [m for m in people_state if m.get("status") == "needs_help"]
    not_safe_people = unaccounted_people + needs_help_people
    
    level = 0
    if not_safe_people:
        if elapsed_minutes < ESCALATION_MINUTES[0]:
            level = 0
        elif elapsed_minutes < ESCALATION_MINUTES[1]:
            level = 1
        elif elapsed_minutes < ESCALATION_MINUTES[2]:
            level = 2
        else:
            level = 3
            
    def is_vulnerable(m_id) -> bool:
        p = plan_by_id.get(m_id, {})
        sl = p.get("support_level", "independent")
        mn = p.get("mobility_needs")
        return sl != "independent" or bool(mn)
        
    def sort_key(m: Dict[str, Any]):
        return (not is_vulnerable(m.get("member_id")), m.get("name", ""))
        
    ordered = sorted(unaccounted_people, key=sort_key)
    ordered_help = sorted(needs_help_people, key=sort_key)
    
    def join_names(names: List[str]) -> str:
        if not names: return ""
        if len(names) == 1: return names[0]
        return ", ".join(names[:-1]) + f" and {names[-1]}"
        
    def join_names_capped(names: List[str]) -> str:
        if not names: return ""
        if len(names) <= 6:
            return join_names(names)
        return join_names(names[:6]) + f" and {len(names)-6} more"
        
    raw_steps = []
    def add_step(priority, who, action, reason=""):
        raw_steps.append({
            "priority": priority,
            "who": who,
            "action": action,
            "reason": reason
        })
        
    if needs_help_people:
        add_step(0, None, "If anyone is in immediate danger, call your local emergency number")
        for p in ordered_help:
            add_step(0, p["name"], f"Help {p['name']}", p.get("note") or "")
            
    for p in ordered[:6]:
        if level == 0:
            add_step(1, p["name"], f"Check that {p['name']} is safe")
        else:
            add_step(1, p["name"], f"Call {p['name']} directly")
            
    if len(ordered) > 6:
        more_names = join_names([p["name"] for p in ordered[6:]])
        add_step(1, None, f"Also check on {len(ordered)-6} more: {more_names}")
            
    contacts = sorted(plan.get("contacts", []), key=lambda c: c.get("priority", 999))
    contact_targets = sorted(not_safe_people, key=sort_key)
    contact_targets_str = join_names([p["name"] for p in contact_targets])
    
    if level >= 2:
        if not contacts:
            add_step(2, None, f"No emergency contacts are saved. Ask a neighbor or local authorities to help check on {contact_targets_str}")
        else:
            c1 = contacts[0]
            add_step(2, c1["name"], f"Contact {c1['name']} and ask them to help check on {contact_targets_str}", f"Phone: {c1.get('phone', '')}")
            
    if level >= 3:
        if len(contacts) > 1:
            c2 = contacts[1]
            add_step(3, c2["name"], f"Contact {c2['name']} and ask them to help check on {contact_targets_str}", f"Phone: {c2.get('phone', '')}")
        add_step(3, None, "If you believe anyone may be in danger, call your local emergency number")
        
    not_safe_pets = [m for m in pets_state if m.get("status") != "safe"]
    if not_safe_pets:
        pet_names = join_names([p["name"] for p in not_safe_pets])
        verb = "is" if len(not_safe_pets) == 1 else "are"
        add_step(5, None, f"Confirm where {pet_names} {verb}")
        
    if not members_state:
        # Empty state
        next_steps = []
        speakable_str = "No one has been added to this check-in yet."
        hh_name = plan.get("name", "Household")
        draft_msg = f"R.I.S.E. check-in for {hh_name}. No one has been added yet."
    else:
        if all_accounted_for:
            add_step(9, None, "Everyone is confirmed safe. Close the check-in when you are ready.")
            
        dedup = []
        seen = set()
        for s in raw_steps:
            k = (s["priority"], s["who"], s["action"], s["reason"])
            if k not in seen:
                seen.add(k)
                dedup.append(s)
                
        def step_sort_key(s):
            if not s["who"]:
                vuln = 0
            else:
                m_id = next((m.get("member_id") for m in members_state if m.get("name") == s["who"]), None)
                vuln = 0 if is_vulnerable(m_id) else 1
            return (s["priority"], vuln, s["who"] or "")
            
        dedup.sort(key=step_sort_key)
        next_steps = dedup[:10]
        
        speakable_parts = []
        if all_accounted_for:
            speakable_parts.append("Everyone is confirmed safe.")
        else:
            num_people = len(people_state)
            safe_people = [m for m in people_state if m.get("status") == "safe"]
            num_safe = len(safe_people)
            if num_people == 0:
                speakable_parts.append("There are no people in this check-in.")
            elif num_people == 1:
                speakable_parts.append(f"{num_safe} of 1 person is confirmed safe.")
            else:
                speakable_parts.append(f"{num_safe} of {num_people} people are confirmed safe.")
                
            if ordered_help:
                n = join_names([p["name"] for p in ordered_help])
                verb = "needs" if len(ordered_help) == 1 else "need"
                speakable_parts.append(f"{n} {verb} help.")
                
            if ordered:
                n = join_names([p["name"] for p in ordered])
                verb = "has" if len(ordered) == 1 else "have"
                speakable_parts.append(f"{n} {verb} not responded.")
                
            if not_safe_pets:
                n = join_names([p["name"] for p in not_safe_pets])
                speakable_parts.append(f"{n} not yet confirmed.")
                
        speakable_str = " ".join(speakable_parts)
        
        safe_names_capped = join_names_capped([m["name"] for m in people_state if m.get("status") == "safe"]) or "none"
        help_parts = []
        for m in ordered_help:
            note = m.get("note")
            if note:
                if len(note) > 60:
                    note = note[:57] + "..."
                help_parts.append(f"{m['name']} ({note})")
            else:
                help_parts.append(m["name"])
        help_str_capped = join_names_capped(help_parts) or "none"
        unreached_str_capped = join_names_capped([p["name"] for p in ordered]) or "none"
        
        hh_name = plan.get("name", "Household")
        draft_msg = f"R.I.S.E. check-in for {hh_name}. Safe: {safe_names_capped}. Needs help: {help_str_capped}. Not yet reached: {unreached_str_capped}."
        if ordered:
            draft_msg += f" Please help check on {unreached_str_capped}."
            
        if len(draft_msg) > 600:
            num_safe = len([m for m in people_state if m.get("status") == "safe"])
            num_help = len(ordered_help)
            num_pending = len(ordered)
            draft_msg = f"R.I.S.E. check-in for {hh_name}. {num_safe} safe, {num_help} need help, {num_pending} not yet reached."
            
    return {
        "counts": counts,
        "all_accounted_for": all_accounted_for,
        "elapsed_minutes": elapsed_minutes,
        "level": level,
        "speakable": speakable_str,
        "next_steps": next_steps,
        "draft_message": draft_msg,
        "disclaimer": DISCLAIMER
    }
