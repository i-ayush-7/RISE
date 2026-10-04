from typing import Dict, Any, List

ESCALATION_MINUTES = (5, 10, 20)
"""These are demo defaults, not official guidance."""

DISCLAIMER = "R.I.S.E. does not contact anyone. Use your phone to call or message. If anyone is in immediate danger, call your local emergency number."

def build_escalation(plan: Dict[str, Any], state: Dict[str, Any], now: Any) -> Dict[str, Any]:
    members_plan = plan.get("members", [])
    members_state = state.get("members", []) if state else []
    
    # Enrich state with plan info
    plan_by_name = {m["name"]: m for m in members_plan}
    
    counts = {"safe": 0, "needs_help": 0, "pending": 0, "not_responding": 0, "total": len(members_state)}
    all_accounted_for = True
    
    for m in members_state:
        status = m.get("status", "pending")
        if status in counts:
            counts[status] += 1
        if status != "safe":
            all_accounted_for = False
            
    # Calculate elapsed
    started_at_str = state.get("started_at") if state else now.isoformat()
    
    # We must not use the standard now function or similar. We parse strings manually or expect the caller to pass an aware datetime.
    # Actually, we can use datetime.fromisoformat since it is standard library, but we just shouldn't call it inside here.
    from datetime import datetime
    started_at = datetime.fromisoformat(started_at_str)
    elapsed_td = now - started_at
    elapsed_minutes = max(0, int(elapsed_td.total_seconds() // 60))
    
    # People (non-pets)
    people_state = [m for m in members_state if not m.get("is_pet")]
    pets_state = [m for m in members_state if m.get("is_pet")]
    
    unaccounted_people = [m for m in people_state if m.get("status") in ("pending", "not_responding")]
    needs_help_people = [m for m in people_state if m.get("status") == "needs_help"]
    
    not_safe_people = unaccounted_people + needs_help_people
    
    level = 0
    if not_safe_people:
        if elapsed_minutes < 5:
            level = 0
        elif elapsed_minutes < 10:
            level = 1
        elif elapsed_minutes < 20:
            level = 2
        else:
            level = 3
            
    def is_vulnerable(name: str) -> bool:
        p = plan_by_name.get(name, {})
        sl = p.get("support_level", "independent")
        mn = p.get("mobility_needs")
        return sl != "independent" or bool(mn)
        
    def sort_key_unaccounted(m: Dict[str, Any]):
        return (not is_vulnerable(m["name"]), m["name"])
        
    unaccounted_people_sorted = sorted(unaccounted_people, key=sort_key_unaccounted)
    
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
        for p in needs_help_people:
            add_step(0, p["name"], f"Help {p['name']}", p.get("note") or "")
            
    for i, p in enumerate(unaccounted_people_sorted[:6]):
        if level == 0:
            add_step(1, p["name"], f"Ask {p['name']} to confirm they are safe")
        else:
            add_step(1, p["name"], f"Call {p['name']} directly")
            
    contacts = sorted(plan.get("contacts", []), key=lambda c: c.get("priority", 999))
    unacc_names = [p["name"] for p in unaccounted_people_sorted]
    unacc_str = ", ".join(unacc_names)
    
    if level >= 2:
        if not contacts:
            add_step(2, None, f"No emergency contacts are saved. Ask a neighbor or local authorities to help check on {unacc_str}")
        else:
            c1 = contacts[0]
            add_step(2, c1["name"], f"Contact {c1['name']} and ask them to help check on {unacc_str}", f"Phone: {c1.get('phone', '')}")
            
    if level >= 3:
        if len(contacts) > 1:
            c2 = contacts[1]
            add_step(3, c2["name"], f"Contact {c2['name']} and ask them to help check on {unacc_str}", f"Phone: {c2.get('phone', '')}")
        add_step(3, None, "If you believe anyone may be in danger, call your local emergency number")
        
    not_safe_pets = [m for m in pets_state if m.get("status") != "safe"]
    if not_safe_pets:
        pet_names = " and ".join(p["name"] for p in not_safe_pets)
        add_step(5, None, f"Confirm where {pet_names} are")
        
    if all_accounted_for:
        add_step(9, None, "Everyone is confirmed safe. Close the check-in when you are ready.")
        
    # Deduplicate keeping order
    dedup = []
    seen = set()
    for s in raw_steps:
        k = (s["priority"], s["who"], s["action"], s["reason"])
        if k not in seen:
            seen.add(k)
            dedup.append(s)
            
    dedup.sort(key=lambda x: (x["priority"], x["who"] or ""))
    next_steps = dedup[:10]
    
    def join_names(names: List[str]) -> str:
        if not names: return ""
        if len(names) == 1: return names[0]
        return ", ".join(names[:-1]) + f" and {names[-1]}"
        
    speakable_parts = []
    if all_accounted_for:
        speakable_parts.append("Everyone is confirmed safe.")
    else:
        num_people = len(people_state)
        safe_people = [m for m in people_state if m.get("status") == "safe"]
        num_safe = len(safe_people)
        if num_people == 1 and num_safe == 1:
            speakable_parts.append("1 of 1 person is confirmed safe.")
        else:
            speakable_parts.append(f"{num_safe} of {num_people} people are confirmed safe.")
            
        if needs_help_people:
            n = join_names([p["name"] for p in needs_help_people])
            verb = "needs" if len(needs_help_people) == 1 else "need"
            speakable_parts.append(f"{n} {verb} help.")
            
        if unaccounted_people:
            n = join_names([p["name"] for p in unaccounted_people])
            verb = "has" if len(unaccounted_people) == 1 else "have"
            speakable_parts.append(f"{n} {verb} not responded.")
            
        if not_safe_pets:
            n = join_names([p["name"] for p in not_safe_pets])
            speakable_parts.append(f"{n} not yet confirmed.")
            
    safe_names = join_names([m["name"] for m in people_state if m.get("status") == "safe"]) or "none"
    help_parts = []
    for m in needs_help_people:
        if m.get("note"):
            help_parts.append(f"{m['name']} ({m['note']})")
        else:
            help_parts.append(m["name"])
    help_str = join_names(help_parts) or "none"
    unreached_str = join_names([p["name"] for p in unaccounted_people]) or "none"
    
    hh_name = plan.get("name", "Household")
    draft_msg = f"R.I.S.E. check-in for {hh_name}. Safe: {safe_names}. Needs help: {help_str}. Not yet reached: {unreached_str}."
    if unaccounted_people:
        draft_msg += f" Please help check on {unreached_str}."
        
    draft_msg = draft_msg[:600]

    return {
        "counts": counts,
        "all_accounted_for": all_accounted_for,
        "elapsed_minutes": elapsed_minutes,
        "level": level,
        "speakable": " ".join(speakable_parts),
        "next_steps": next_steps,
        "draft_message": draft_msg,
        "disclaimer": DISCLAIMER
    }
