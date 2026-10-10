from bff.intents import parse_intent

async def handle_chat(text: str, run_tool) -> dict:
    ok, plan, ms = await run_tool("get_household_plan", {})
    if not ok:
        return {
            "reply": "I could not read the household plan right now.",
            "intent": "error",
            "tools": [{"name": "get_household_plan", "ok": False}],
            "refresh": []
        }
    
    members = []
    for m in plan.get("members", []):
        members.append({"name": m["name"], "is_pet": 1 if m.get("is_pet") else 0})
        
    intent_data = parse_intent(text, members)
    intent = intent_data.get("intent")
    
    tools = [{"name": "get_household_plan", "ok": True}]
    refresh = []
    reply = ""
    
    if intent == "record":
        status = intent_data["status"]
        names = intent_data["names"]
        note = intent_data.get("note")
        
        tools_run = []
        all_ok = True
        err_msg = ""
        for name in names:
            args = {"member_name": name, "status": status}
            if note:
                args["note"] = note
            ok_r, res_r, _ = await run_tool("record_checkin", args)
            tools_run.append({"name": "record_checkin", "ok": ok_r})
            if not ok_r:
                all_ok = False
                err_msg = res_r
                break
        
        tools.extend(tools_run)
        
        if not all_ok:
            r = err_msg
            if isinstance(err_msg, str) and "No check-in is active" in err_msg:
                r += ' Say "start a check-in" first.'
            return {"reply": r, "intent": intent, "tools": tools, "refresh": []}
            
        ok_s, res_s, _ = await run_tool("get_checkin_status", {})
        tools.append({"name": "get_checkin_status", "ok": ok_s})
        
        speakable = res_s.get("speakable", "") if ok_s else ""
        refresh.append("checkin")
        
        joined_names = " and ".join(names)
        if status == "needs_help":
            reply = f"If anyone is in immediate danger, call your local emergency number. Marked {joined_names} as needing help. {speakable}".strip()
        elif status == "not_responding":
            reply = f"Marked {joined_names} as not responding. {speakable}".strip()
        else:
            reply = f"Marked {joined_names} as safe. {speakable}".strip()
            
    elif intent == "start_checkin":
        ok_sc, res_sc, _ = await run_tool("start_checkin", {"reason": "Chat check-in"})
        tools.append({"name": "start_checkin", "ok": ok_sc})
        refresh.append("checkin")
        if ok_sc:
            reply = 'Check-in started. Everyone is pending. Tell me who is safe by name.'
        else:
            reply = res_sc
            
    elif intent == "status":
        ok_st, res_st, _ = await run_tool("get_checkin_status", {})
        tools.append({"name": "get_checkin_status", "ok": ok_st})
        refresh.append("checkin")
        if ok_st:
            reply = res_st.get("speakable", "")
            next_steps = res_st.get("next_steps", [])
            if next_steps:
                reply += " Next: " + next_steps[0]["action"]
        else:
            reply = 'No check-in is active. Say "start a check-in" to begin.'
            
    elif intent == "people_needing_help":
        ok_ph, res_ph, _ = await run_tool("list_people_needing_help", {})
        tools.append({"name": "list_people_needing_help", "ok": ok_ph})
        if ok_ph and len(res_ph) > 0:
            names_str = " and ".join([p["name"] for p in res_ph])
            reply = f"{names_str} may need extra help."
        else:
            reply = "No one in the plan is marked as needing extra help."
            
    elif intent == "alerts":
        ok_a, res_a, _ = await run_tool("get_active_alerts", {})
        tools.append({"name": "get_active_alerts", "ok": ok_a})
        refresh.append("alerts")
        if not ok_a:
            if isinstance(res_a, str) and res_a.startswith("The live alert service could not be reached"):
                reply = res_a
            else:
                reply = res_a
        else:
            alerts = res_a.get("alerts", [])
            data_mode = res_a.get("data_mode", "")
            
            if data_mode == "simulated":
                mode_phrase = "Simulated alert:"
            elif data_mode == "recorded":
                mode_phrase = "Replay of a past alert, not live:"
            else:
                mode_phrase = "Live alert:"
                
            if not alerts:
                reply = f"No active alerts right now. ({data_mode} data)"
            else:
                replies = []
                for a in alerts[:2]:
                    inst = a.get("instruction", "")
                    if len(inst) > 400:
                        inst = inst[:397] + "..."
                    replies.append(f"{mode_phrase} {a.get('headline')}. {inst}".strip())
                reply = "\n\n".join(replies)
                
    elif intent == "advice":
        ok_ad, res_ad, _ = await run_tool("get_safety_advice", {})
        tools.append({"name": "get_safety_advice", "ok": ok_ad})
        refresh.extend(["advice", "alerts"])
        if not ok_ad:
            if isinstance(res_ad, str) and res_ad.startswith("The live alert service could not be reached"):
                reply = res_ad
            else:
                reply = res_ad
        else:
            headline = res_ad.get("headline", "")
            actions = res_ad.get("actions", [])
            action_strs = [a["action"] for a in actions[:3]]
            reply = f"{headline} Top actions: " + "; ".join(action_strs)
            
    elif intent == "household":
        reply = plan.get("summary", "")
        
    elif intent == "close_hint":
        reply = "Use the Close check-in button on the Board screen; it asks for confirmation."
        
    elif intent == "mark_all_refused":
        reply = 'I only record people you name. Tell me who is safe, for example "Maria is safe".'
        
    elif intent == "clarify_not_safe":
        names = intent_data.get("names", [])
        joined = " and ".join(names)
        fn = names[0].split()[0] if names else "Someone"
        reply = f'Do you want me to mark {joined} as needing help? Say it plainly, for example "{fn} needs help".'
        
    elif intent == "confirm_needed":
        names = intent_data.get("names", [])
        joined = " and ".join(names)
        fn = names[0].split()[0] if names else "Someone"
        hint = intent_data.get("hint_status")
        if hint == "needs_help":
            adjective = "needing help"
            example = f'"{fn} needs help"'
        elif hint == "not_responding":
            adjective = "not responding"
            example = f'"{fn} isn\'t answering"'
        else:
            adjective = "safe"
            example = f'"{fn} is safe"'
        reply = f'I only record clear statements about what is true right now. If you want me to mark {joined} as {adjective}, say it plainly, for example {example}.'
        
    elif intent == "clarify_negated":
        names = intent_data.get("names", [])
        joined = " and ".join(names)
        fn = names[0].split()[0] if names else "Someone"
        reply = f'I\'m not sure what you mean about {joined}. Tell me plainly, for example "{fn} is safe" or "{fn} needs help".'
        
    elif intent == "clarify_multiple":
        reply = 'Please tell me one status at a time, for example "Maria is safe" and then "Elena needs help".'
        
    elif intent == "clarify_one_person":
        reply = "Please tell me about one person at a time when someone needs help."
        
    elif intent == "ambiguous":
        cands = intent_data.get("candidates", [])
        joined = " or ".join(cands)
        reply = f"Which one do you mean: {joined}?"
        
    elif intent == "refuse":
        reply = 'I can\'t act on that. Tell me what happened, for example "Maria is safe".'
        
    elif intent == "invalid":
        reply = "Please type a short message (up to 200 characters)."
        
    else:
        reply = 'I can help with check-ins and safety info. Try saying "Start a check-in", "Maria is safe", "What should we do?", or "Any alerts?".'
        
    return {
        "reply": reply,
        "intent": intent,
        "tools": tools,
        "refresh": refresh
    }
