import re
import unicodedata
from typing import List, Dict, Any

def parse_intent(text: Any, members: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(text, str):
        return {"intent": "invalid"}

    chars = []
    for c in text:
        cat = unicodedata.category(c)
        if cat in ("Cc", "Cf"):
            if c in ("\n", "\r", "\t"):
                chars.append(" ")
        else:
            chars.append(c)
            
    cleaned = "".join(chars)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if not cleaned or len(cleaned) > 200:
        return {"intent": "invalid"}
        
    lower_text = cleaned.lower()
    
    names_matched = []
    ambiguous = False
    candidates = []
    
    first_name_to_members = {}
    for m in members:
        fn = m["name"].split()[0].lower()
        if fn not in first_name_to_members:
            first_name_to_members[fn] = []
        first_name_to_members[fn].append(m["name"])
        
    matches = []
    for m in members:
        full = m["name"].lower()
        pattern = r'\b' + re.escape(full) + r'\b'
        for match in re.finditer(pattern, lower_text):
            matches.append({"name": m["name"], "start": match.start(), "type": "full"})
            
    for fn, fnames in first_name_to_members.items():
        pattern = r'\b' + re.escape(fn) + r'\b'
        for match in re.finditer(pattern, lower_text):
            overlap = False
            for fm in matches:
                if fm["type"] == "full" and (fm["start"] <= match.start() < fm["start"] + len(fm["name"])):
                    overlap = True
                    break
            if not overlap:
                matches.append({"start": match.start(), "type": "first", "fn": fn, "candidates": fnames})

    matches.sort(key=lambda x: x["start"])
    
    seen = set()
    for m in matches:
        if m["type"] == "full":
            if m["name"] not in seen:
                names_matched.append(m["name"])
                seen.add(m["name"])
        else:
            cands = m["candidates"]
            if len(cands) == 1:
                if cands[0] not in seen:
                    names_matched.append(cands[0])
                    seen.add(cands[0])
            else:
                ambiguous = True
                candidates = cands
                break
                
    if ambiguous:
        return {"intent": "ambiguous", "candidates": candidates}
        
    is_q = False
    if cleaned.endswith("?"):
        is_q = True
    else:
        q_words = {"is", "are", "was", "were", "did", "does", "do", "has", "have", "can", "could", "where", "how", "what", "why", "who", "when", "will", "should", "would"}
        first_word = lower_text.split()[0]
        if first_word in q_words:
            is_q = True
            
    inj_words = ["ignore previous", "ignore all", "disregard", "system prompt", "override", "developer mode"]
    for w in inj_words:
        if w in lower_text:
            return {"intent": "refuse", "reason": "instructions"}
            
    status_words = ["safe", "okay", "ok", "fine", "accounted for", "needs help", "hurt"]
    all_words = ["everyone", "everybody", "all of them", "the whole family", "all of us", "the family"]
    
    has_status = any(w in lower_text for w in status_words)
    has_all = any(w in lower_text for w in all_words)
    if has_status and has_all:
        return {"intent": "mark_all_refused"}
        
    start_cmds = ["start", "begin", "open", "run", "kick off", "do"]
    chk_words = ["check-in", "check in", "checkin"]
    start_chk = False
    for s in start_cmds:
        for c in chk_words:
            if re.search(r'\b' + re.escape(s) + r'\b.*\b' + re.escape(c) + r'\b', lower_text) or re.search(r'\b' + re.escape(c) + r'\b.*\b' + re.escape(s) + r'\b', lower_text):
                start_chk = True
                break
    for p in ["check on everyone", "check on the family", "account for everyone"]:
        if p in lower_text:
            start_chk = True
    if start_chk:
        return {"intent": "start_checkin"}
        
    close_cmds = ["close", "end", "finish", "stop", "cancel"]
    close_chk = False
    for s in close_cmds:
        for c in chk_words:
            if re.search(r'\b' + re.escape(s) + r'\b.*\b' + re.escape(c) + r'\b', lower_text) or re.search(r'\b' + re.escape(c) + r'\b.*\b' + re.escape(s) + r'\b', lower_text):
                close_chk = True
                break
    if close_chk:
        return {"intent": "close_hint"}
        
    if not is_q and names_matched:
        neg_safe = ["not safe", "isn't safe", "is not ok", "is not okay", "is not fine", "unsafe", "not okay", "not fine", "isn't ok"]
        for p in neg_safe:
            if p in lower_text:
                return {"intent": "clarify_not_safe", "names": names_matched}
                
        needs_words = ["needs help", "need help", "needs an ambulance", "hurt", "injured", "fell", "trapped", "stuck", "can't walk", "cannot walk", "can't move", "cannot move", "bleeding", "unconscious"]
        needs_help_match = False
        for p in needs_words:
            if p in lower_text:
                needs_help_match = True
                break
        if re.search(r'\bmark\b.*\bas needing help\b', lower_text) or re.search(r'\bmark\b.*\bhelp needed\b', lower_text):
            needs_help_match = True
            
        if needs_help_match:
            if len(names_matched) > 1:
                return {"intent": "clarify_one_person"}
            return {"intent": "record", "status": "needs_help", "names": names_matched, "note": cleaned[:300]}
            
        not_resp = ["not answering", "isn't answering", "not responding", "no answer", "can't reach", "cannot reach", "didn't answer", "not picking up", "unreachable"]
        for p in not_resp:
            if p in lower_text:
                return {"intent": "record", "status": "not_responding", "names": names_matched}
                
        safe_words = ["confirmed safe", "checked in", "made it", "arrived safe"]
        safe_match = False
        for p in safe_words:
            if p in lower_text:
                safe_match = True
                break
        if not safe_match:
            if re.search(r'\b(is|are|\'s|was)\s+(safe|okay|ok|fine|accounted for)\b', lower_text):
                safe_match = True
            elif re.search(r'\bmark\b.*\b(as\s+)?(safe|okay)\b', lower_text):
                safe_match = True
                
        if safe_match:
            return {"intent": "record", "status": "safe", "names": names_matched[:5]}
            
    status_phrases = ["how is everyone", "how are we", "status", "who has responded", "who hasn't", "who has not", "who is safe", "who's safe", "is everyone safe", "are we all safe", "everyone ok", "everyone safe", "check-in status", "progress"]
    for p in status_phrases:
        if p in lower_text:
            return {"intent": "status"}
            
    who_needs = ["who needs help", "who needs extra help", "who is vulnerable"]
    for p in who_needs:
        if p in lower_text:
            return {"intent": "people_needing_help"}
            
    alerts_w = ["alert", "alerts", "warning", "warnings", "happening", "weather", "any news"]
    for p in alerts_w:
        if p in lower_text:
            return {"intent": "alerts"}
            
    advice_w = ["what should", "what do we do", "what now", "advice", "prepare", "what's the plan", "next steps", "actions", "evacuate"]
    for p in advice_w:
        if p in lower_text:
            return {"intent": "advice"}
            
    house_w = ["who is in", "household", "members", "the plan", "contacts"]
    for p in house_w:
        if p in lower_text:
            return {"intent": "household"}
            
    if len(names_matched) == 1:
        if is_q:
            return {"intent": "status"}
        else:
            return {"intent": "help"}
            
    return {"intent": "help"}
