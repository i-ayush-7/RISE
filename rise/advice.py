from typing import List, Dict, Any
from rise.alerts import Alert, SEVERITY_RANK

HAZARD_RANK = {
    'flood': 1,
    'cyclone': 2,
    'wildfire': 3,
    'earthquake': 4,
    'heat': 5,
    'cold': 6,
    'storm': 7,
    'other': 8
}

def _get_highest_severity_alerts(alerts: List[Alert]) -> List[Alert]:
    best = {}
    for a in alerts:
        if a.hazard not in best or SEVERITY_RANK[a.severity] > SEVERITY_RANK[best[a.hazard].severity]:
            best[a.hazard] = a
    return list(best.values())

def _people_evac_help(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [m for m in plan.get("members", []) if m.get("is_pet") == 0 and (m.get("support_level") != "independent" or m.get("mobility_needs"))]

def _people_care_help(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [m for m in plan.get("members", []) if m.get("is_pet") == 0 and (m.get("age_group") in ("child", "senior") or m.get("medical_needs"))]

def _is_p1_evac(m: Dict[str, Any]) -> bool:
    if m.get("mobility_needs") or m.get("support_level") == "needs_assistance":
        return True
    if m.get("support_level") == "dependent" and m.get("age_group") != "child":
        return True
    return False

def build_advice(plan: Dict[str, Any], alerts: List[Alert], is_simulated: bool) -> Dict[str, Any]:
    highest_alerts = _get_highest_severity_alerts(alerts)
    highest_alerts.sort(key=lambda a: (-SEVERITY_RANK[a.severity], HAZARD_RANK[a.hazard]))
    
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
    alert_names_list = [f"{a.hazard} {a.severity}" for a in highest_alerts]
    alert_names = ""
    if len(alert_names_list) == 1:
        alert_names = alert_names_list[0]
    elif len(alert_names_list) == 2:
        alert_names = f"{alert_names_list[0]} and {alert_names_list[1]}"
    else:
        alert_names = ", ".join(alert_names_list[:-1]) + f", and {alert_names_list[-1]}"
    
    alert_names = alert_names.capitalize()
    
    dominant_hazard = highest_alerts[0].hazard
    if dominant_hazard in ("flood", "cyclone", "wildfire"):
        help_count = len(_people_evac_help(plan))
        noun = "people" if help_count != 1 else "person"
        help_text = f": {help_count} {noun} need extra help getting out." if help_count > 0 else "."
    elif dominant_hazard in ("heat", "cold"):
        help_count = len(_people_care_help(plan))
        noun = "people" if help_count != 1 else "person"
        help_text = f": {help_count} {noun} need extra care." if help_count > 0 else "."
    elif dominant_hazard == "earthquake":
        help_count = len(_people_evac_help(plan))
        noun = "people" if help_count != 1 else "person"
        help_text = f": {help_count} {noun} may need help after the shaking stops." if help_count > 0 else "."
    else:
        help_count = len(_people_evac_help(plan))
        noun = "people" if help_count != 1 else "person"
        help_text = f": {help_count} {noun} need extra help." if help_count > 0 else "."
        
    headline = f"{alert_names} for {plan.get('name', 'Household')}{help_text}"
    if is_simulated:
        headline = f"This is a simulated alert. {headline}"
        
    # Official Instructions
    official_instructions = []
    # Note: input order, not sorted order
    for a in alerts:
        if a.instructions:
            official_instructions.append({
                "headline": a.headline,
                "instructions": a.instructions
            })
            
    raw_actions = []
    def add_action(priority, who, action, reason, is_mandatory=False):
        raw_actions.append({
            "priority": priority,
            "who": who,
            "action": action,
            "reason": reason or "",
            "_mandatory": is_mandatory
        })

    members = plan.get("members", [])
    people = [m for m in members if m.get("is_pet") == 0]
    pets = [m for m in members if m.get("is_pet") == 1]
    
    contacts = plan.get("contacts", [])
    primary_contact = min(contacts, key=lambda c: c.get("priority", 999)) if contacts else None
        
    meeting_points = plan.get("meeting_points", [])
    primary_mp = next((mp for mp in meeting_points if mp.get("kind") == "primary"), None)

    evacuation_mode = any(a.hazard in ("flood", "cyclone", "wildfire") and SEVERITY_RANK[a.severity] >= 3 for a in highest_alerts)

    for a in highest_alerts:
        sev_rank = SEVERITY_RANK[a.severity]
        
        if a.hazard == "earthquake":
            add_action(0, None, "Drop, cover and hold on", "", True)
            for p in _people_evac_help(plan):
                add_action(2, p["name"], f"Check on {p['name']}", p.get("mobility_needs") or "")
                
        if evacuation_mode:
            if a.hazard in ("flood", "cyclone", "wildfire") and sev_rank >= 3:
                for p in people:
                    if _is_p1_evac(p):
                        add_action(1, p["name"], f"Start moving {p['name']} early and arrange transport", p.get("mobility_needs"))
                    elif p.get("age_group") == "child":
                        add_action(2, p["name"], f"Keep an adult with {p['name']}", "")
                
                if primary_mp:
                    add_action(3, None, f"Head to the primary meeting point: {primary_mp['label']}", "", True)
                else:
                    add_action(3, None, "Choose a safe place to go", "", True)
                    
                if primary_contact:
                    add_action(4, primary_contact["name"], f"Call {primary_contact['name']} first (priority {primary_contact.get('priority', 1)})", "", True)
                
                for p in people:
                    if p.get("medical_needs"):
                        add_action(5, p["name"], f"Gather {p['name']}'s medication and documents", p.get("medical_needs"))

                if pets:
                    pet_names = " and ".join([p["name"] for p in pets])
                    add_action(6, pet_names, f"Gather pet supplies and a carrier for {pet_names}", "")
                    add_action(7, pet_names, "Check that your shelter accepts pets", "")
        else:
            if a.hazard in ("flood", "cyclone", "wildfire"):
                if primary_mp:
                    add_action(6, None, f"Review meeting point: {primary_mp['label']}", "")
                for p in people:
                    if p.get("medical_needs"):
                        add_action(7, p["name"], f"Gather {p['name']}'s medication and documents", p.get("medical_needs"))
                add_action(8, None, "Charge phones and prepare to leave", "")
                
            elif a.hazard == "heat":
                for p in people:
                    if p.get("age_group") in ("child", "senior") or p.get("medical_needs"):
                        add_action(4, p["name"], f"Check on {p['name']} every few hours and keep them cool and hydrated", "")
                if pets:
                    pet_names = " and ".join([p["name"] for p in pets])
                    add_action(5, pet_names, f"Provide shade and water for {pet_names}", "")
                    
            elif a.hazard == "cold":
                for p in people:
                    if p.get("age_group") in ("child", "senior") or p.get("medical_needs"):
                        add_action(4, p["name"], f"Check on {p['name']} every few hours and keep them warm", "")
                if pets:
                    pet_names = " and ".join([p["name"] for p in pets])
                    add_action(5, pet_names, f"Provide warm shelter and water for {pet_names}", "")
                    
            elif a.hazard in ("storm", "other"):
                if sev_rank >= 3:
                    add_action(3, None, "Stay indoors and keep phones charged", "")
                else:
                    add_action(3, None, "Keep phones charged and watch for updates", "")
                for p in _people_evac_help(plan):
                    add_action(4, p["name"], f"Check on {p['name']}", "")
                
    # Deduplicate keeping lowest priority
    dedup = {}
    for act in raw_actions:
        key = (act["who"], act["action"], act["reason"])
        if key not in dedup or act["priority"] < dedup[key]["priority"]:
            dedup[key] = act
            
    final_actions = list(dedup.values())
    final_actions.sort(key=lambda x: (x["priority"], x["who"] or ""))
    
    # Cap at 8, preserving mandatory actions
    if len(final_actions) > 8:
        mandatory = [a for a in final_actions if a["_mandatory"]]
        optional = [a for a in final_actions if not a["_mandatory"]]
        optional.sort(key=lambda x: (x["priority"], x["who"] or ""))
        
        slots_left = 8 - len(mandatory)
        kept_optional = optional[:slots_left]
        
        final_actions = mandatory + kept_optional
        final_actions.sort(key=lambda x: (x["priority"], x["who"] or ""))
        
    for a in final_actions:
        del a["_mandatory"]
    
    return {
        "is_simulated": is_simulated,
        "urgency": urgency,
        "headline": headline,
        "official_instructions": official_instructions,
        "actions": final_actions,
        "disclaimer": "This is general preparedness guidance from your saved household plan. Follow instructions from local authorities."
    }
