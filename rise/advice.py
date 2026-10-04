from typing import List, Dict, Any
from rise.alerts import Alert, SEVERITY_RANK

def _get_highest_severity_alerts(alerts: List[Alert]) -> List[Alert]:
    best = {}
    for a in alerts:
        if a.hazard not in best or SEVERITY_RANK[a.severity] > SEVERITY_RANK[best[a.hazard].severity]:
            best[a.hazard] = a
    return list(best.values())

def _people_needing_help(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    people = [m for m in plan.get("members", []) if m.get("is_pet") == 0]
    return [m for m in people if m.get("support_level") != "independent" or m.get("mobility_needs") or m.get("medical_needs")]

def _is_child_or_dependent(m: Dict[str, Any]) -> bool:
    return m.get("age_group") == "child" or m.get("support_level") == "dependent"

def _is_senior_child_medical(m: Dict[str, Any]) -> bool:
    return m.get("age_group") in ("child", "senior") or bool(m.get("medical_needs"))

def build_advice(plan: Dict[str, Any], alerts: List[Alert], is_simulated: bool) -> Dict[str, Any]:
    highest_alerts = _get_highest_severity_alerts(alerts)
    
    if not highest_alerts:
        headline = f"No active alerts for {plan.get('name', 'Household')}."
        if is_simulated:
            headline = f"This is a simulated alert. {headline}"
            
        return {
            "is_simulated": is_simulated,
            "urgency": "none",
            "headline": headline,
            "official_instructions": [],
            "actions": [],
            "disclaimer": "This is general preparedness guidance from your saved household plan. Follow instructions from local authorities."
        }

    # Urgency
    max_sev = max(SEVERITY_RANK[a.severity] for a in highest_alerts)
    urgency_map = {1: "low", 2: "low", 3: "high", 4: "immediate"}
    urgency = urgency_map[max_sev]
    
    # Headline
    alert_names = " and ".join(sorted(f"{a.hazard.capitalize()} {a.severity}" for a in highest_alerts))
    help_needs = _people_needing_help(plan)
    help_count = len(help_needs)
    if help_count == 1:
        help_text = ": 1 person needs extra help getting out."
    elif help_count > 1:
        help_text = f": {help_count} people need extra help getting out."
    else:
        help_text = "."
        
    headline = f"{alert_names} for {plan.get('name', 'Household')}{help_text}"
    if is_simulated:
        headline = f"This is a simulated alert. {headline}"
        
    # Official Instructions
    official_instructions = []
    for a in alerts:
        if a.instructions:
            official_instructions.append({
                "headline": a.headline,
                "instructions": a.instructions
            })
            
    raw_actions = []
    def add_action(priority, who, action, reason):
        raw_actions.append({
            "priority": priority,
            "who": who,
            "action": action,
            "reason": reason or ""
        })

    members = plan.get("members", [])
    people = [m for m in members if m.get("is_pet") == 0]
    pets = [m for m in members if m.get("is_pet") == 1]
    
    contacts = plan.get("contacts", [])
    primary_contact = None
    if contacts:
        primary_contact = min(contacts, key=lambda c: c.get("priority", 999))
        
    meeting_points = plan.get("meeting_points", [])
    primary_mp = next((mp for mp in meeting_points if mp.get("kind") == "primary"), None)

    for a in highest_alerts:
        sev_rank = SEVERITY_RANK[a.severity]
        
        # Evacuation hazards
        if a.hazard in ("flood", "cyclone", "wildfire"):
            if sev_rank >= 3: # warning or emergency
                for p in people:
                    if p.get("support_level") != "independent" or p.get("mobility_needs"):
                        add_action(1, p["name"], f"Start moving {p['name']} early and arrange transport", p.get("mobility_needs"))
                    if _is_child_or_dependent(p):
                        add_action(2, p["name"], f"Keep an adult with {p['name']}", "")
                if pets:
                    pet_names = " and ".join([p["name"] for p in pets])
                    add_action(3, pet_names, f"Gather pet supplies and a carrier for {pet_names}", "")
                    add_action(3, pet_names, "Check that your shelter accepts pets", "")
                
                if primary_mp:
                    add_action(4, None, f"Head to the primary meeting point: {primary_mp['label']}", "")
                else:
                    add_action(4, None, "Choose a safe place to go", "")
                    
                if primary_contact:
                    add_action(5, primary_contact["name"], f"Call {primary_contact['name']} first (priority {primary_contact.get('priority', 1)})", "")
                    
            else: # watch or advisory
                if primary_mp:
                    add_action(6, None, f"Review meeting point: {primary_mp['label']}", "")
                for p in people:
                    if p.get("medical_needs"):
                        add_action(7, p["name"], f"Gather {p['name']}'s medication and documents", p.get("medical_needs"))
                add_action(8, None, "Charge phones and prepare to leave", "")
                
        elif a.hazard == "heat":
            for p in people:
                if _is_senior_child_medical(p):
                    add_action(4, p["name"], f"Check on {p['name']} every few hours and keep them cool and hydrated", "")
            if pets:
                pet_names = " and ".join([p["name"] for p in pets])
                add_action(5, pet_names, f"Provide shade and water for {pet_names}", "")
                
        elif a.hazard == "cold":
            for p in people:
                if _is_senior_child_medical(p):
                    add_action(4, p["name"], f"Check on {p['name']} every few hours and keep them warm", "")
            if pets:
                pet_names = " and ".join([p["name"] for p in pets])
                add_action(5, pet_names, f"Provide warm shelter and water for {pet_names}", "")
                
        elif a.hazard == "earthquake":
            add_action(1, None, "Drop, cover and hold on", "")
            for p in people:
                if p.get("mobility_needs"):
                    add_action(2, p["name"], f"Check on {p['name']}", p.get("mobility_needs"))
                    
        else: # storm, other
            add_action(3, None, "Stay indoors and keep phones charged", "")
            for p in help_needs:
                add_action(4, p["name"], f"Check on {p['name']}", "")
                
    # Deduplicate keeping lowest priority
    dedup = {}
    for act in raw_actions:
        key = (act["who"], act["action"], act["reason"])
        if key not in dedup or act["priority"] < dedup[key]["priority"]:
            dedup[key] = act
            
    final_actions = list(dedup.values())
    final_actions.sort(key=lambda x: (x["priority"], x["action"]))
    
    return {
        "is_simulated": is_simulated,
        "urgency": urgency,
        "headline": headline,
        "official_instructions": official_instructions,
        "actions": final_actions[:8],
        "disclaimer": "This is general preparedness guidance from your saved household plan. Follow instructions from local authorities."
    }
