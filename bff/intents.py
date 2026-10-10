import re
import unicodedata
from typing import List, Dict, Any

def has_phrase(phrases: List[str], text: str) -> bool:
    for p in phrases:
        if re.search(r'\b' + re.escape(p) + r'\b', text):
            return True
    return False

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
    name_spans = []
    for m in matches:
        if m["type"] == "full":
            name_len = len(m["name"])
            name_val = m["name"]
            cands = [m["name"]]
        else:
            name_len = len(m["fn"])
            name_val = m["candidates"][0] if len(m["candidates"]) == 1 else m["fn"]
            cands = m["candidates"]
            
        if len(cands) == 1:
            name_spans.append((m["start"], m["start"] + name_len))
            if name_val not in seen:
                names_matched.append(name_val)
                seen.add(name_val)
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
    if has_phrase(inj_words, lower_text):
        return {"intent": "refuse", "reason": "instructions"}
        
    all_words = ["everyone", "everybody", "all of them", "the whole family", "all of us", "the family"]
    has_all = has_phrase(all_words, lower_text)
    
    status_phrases = ["how is everyone", "who has responded", "is everyone safe", "are we all safe", "everyone ok", "everyone safe", "check-in status", "progress", "how is the family", "is the family safe", "is the whole family okay"]
    if has_all:
        if not has_phrase(["mark"], lower_text) and (is_q or has_phrase(status_phrases, lower_text)):
            return {"intent": "status"}
        status_words = ["safe", "okay", "ok", "fine", "accounted for", "needs help", "hurt"]
        if not is_q and has_phrase(status_words, lower_text):
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
        if has_phrase([p], lower_text):
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
        hedge_words = ["if", "unless", "whether", "maybe", "perhaps", "probably", "possibly", "might", "i think", "i guess", "i hope", "hopefully", "i believe", "i suppose", "i assume", "not sure", "unsure", "should be", "could be", "seems", "apparently", "supposedly", "tell me", "let me know", "wondering", "i wonder", "no idea", "dunno"]
        attr_words = ["says", "said", "told", "texted", "messaged", "called", "heard", "claims", "reported", "according to", "relayed"]
        tense_words = ["was", "were", "will", "would", "going to", "gonna", "used to", "earlier", "yesterday", "last night", "before", "soon", "later", "tomorrow", "no longer", "once", "until"]
        
        gate1_phrases = hedge_words + attr_words + tense_words
        if has_phrase(gate1_phrases, lower_text):
            hint = None
            if has_phrase(["safe", "okay", "ok", "fine", "accounted for"], lower_text):
                hint = "safe"
            elif has_phrase(["needs help", "need help", "hurt", "injured"], lower_text):
                hint = "needs_help"
            elif has_phrase(["not answering", "not responding", "can't reach"], lower_text):
                hint = "not_responding"
            return {"intent": "confirm_needed", "names": names_matched, "hint_status": hint}

        needs_phrases = ["needs help", "need help", "needs an ambulance", "help needed", "needs rescue", "hurt", "injured", "injury", "fell", "fallen", "collapsed", "fainted", "trapped", "stuck", "bleeding", "unconscious", "unresponsive", "in pain", "chest pain", "not breathing", "can't breathe", "cannot breathe", "can't walk", "cannot walk", "can't move", "cannot move", "can't stand", "cannot stand", "can't get up", "cannot get up"]
        needs_re = r'\bmark\b.*\bas needing help\b|\bmark\b.*\bhelp needed\b'
        
        not_resp_phrases = ["not answering", "isn't answering", "aren't answering", "are not answering", "not responding", "isn't responding", "aren't responding", "are not responding", "no answer", "no response", "can't reach", "cannot reach", "didn't answer", "not picking up", "unreachable", "hasn't answered", "has not answered", "hasn't responded", "has not responded"]
        
        temp_text = lower_text
        for p in needs_phrases + not_resp_phrases:
            temp_text = re.sub(r'\b' + re.escape(p) + r'\b', '', temp_text)
        temp_text = re.sub(needs_re, '', temp_text)
        
        neg_words = ["not", "no", "never", "none", "nobody", "nor", "without", "hardly", "barely", "cannot", "cant"]
        has_neg = has_phrase(neg_words, temp_text)
        if re.search(r'\b\w+n\'t\b', temp_text):
            has_neg = True
            
        all_status_words = ["safe", "okay", "ok", "fine", "accounted for", "hurt", "injured", "needs help", "need help", "checked in", "answering", "responding"]
        neg_safe = ["not safe", "isn't safe", "is not ok", "is not okay", "is not fine", "unsafe", "not okay", "not fine", "isn't ok", "isn't okay"]
        if has_phrase(neg_safe, lower_text):
            return {"intent": "clarify_not_safe", "names": names_matched}
        elif has_neg and has_phrase(all_status_words, lower_text):
            return {"intent": "clarify_negated", "names": names_matched}

        has_safe = False
        has_needs = False
        has_not_resp = False
        
        safe_phrases = ["confirmed safe", "checked in", "made it", "arrived safe"]
        if has_phrase(safe_phrases, lower_text) or re.search(r"\b(is|are|\'s)\s+(both\s+|all\s+)?(safe|okay|ok|fine|accounted for)\b", lower_text) or re.search(r'\bmark\b.*\b(as\s+)?(safe|okay)\b', lower_text):
            has_safe = True
            
        if has_phrase(needs_phrases, lower_text) or re.search(needs_re, lower_text):
            has_needs = True
            
        if has_phrase(not_resp_phrases, lower_text):
            has_not_resp = True
            
        cats = sum([1 for x in [has_safe, has_needs, has_not_resp] if x])
        if cats > 1:
            return {"intent": "clarify_multiple"}
            
        if len(names_matched) > 1:
            gate4_text = list(lower_text)
            for start, end in reversed(name_spans):
                gate4_text[start:end] = [" "] * (end - start)
            gate4_text = "".join(gate4_text)
            
            for p in safe_phrases + needs_phrases + not_resp_phrases:
                gate4_text = re.sub(r'\b' + re.escape(p) + r'\b', ' ', gate4_text)
            gate4_text = re.sub(r"\b(is|are|\'s)\s+(both\s+|all\s+)?(safe|okay|ok|fine|accounted for)\b", ' ', gate4_text)
            gate4_text = re.sub(r'\bmark\b.*\b(as\s+)?(safe|okay)\b', ' ', gate4_text)
            gate4_text = re.sub(needs_re, ' ', gate4_text)
            
            gate4_text = re.sub(r'[^\w\s\']', ' ', gate4_text)
            gate4_text = gate4_text.replace("'", " ")
            
            connectors = {"and", "both", "all", "are", "is", "as", "mark", "please", "set", "note", "record", "confirm", "that", "the", "also", "s"}
            remaining_words = gate4_text.split()
            for w in remaining_words:
                if w not in connectors:
                    return {"intent": "clarify_multiple"}
                    
        if has_needs:
            if len(names_matched) > 1:
                return {"intent": "clarify_one_person"}
            return {"intent": "record", "status": "needs_help", "names": names_matched, "note": cleaned[:300]}
            
        if has_not_resp:
            return {"intent": "record", "status": "not_responding", "names": names_matched}
            
        if has_safe:
            return {"intent": "record", "status": "safe", "names": names_matched[:5]}
            
    more_status = ["how is everyone", "how are we", "status", "who has responded", "who hasn't", "who has not", "who is safe", "who's safe", "is everyone safe", "are we all safe", "everyone ok", "everyone safe", "check-in status", "progress"]
    if has_phrase(more_status, lower_text):
        return {"intent": "status"}
            
    who_needs = ["who needs help", "who needs extra help", "who is vulnerable"]
    if has_phrase(who_needs, lower_text):
        return {"intent": "people_needing_help"}
            
    alerts_w = ["alert", "alerts", "warning", "warnings", "happening", "weather", "any news"]
    if has_phrase(alerts_w, lower_text):
        return {"intent": "alerts"}
            
    advice_w = ["what should", "what do we do", "what now", "advice", "prepare", "what's the plan", "next steps", "actions", "evacuate"]
    if has_phrase(advice_w, lower_text):
        return {"intent": "advice"}
            
    house_w = ["who is in", "household", "members", "the plan", "contacts"]
    if has_phrase(house_w, lower_text):
        return {"intent": "household"}
            
    if len(names_matched) == 1:
        if is_q:
            return {"intent": "status"}
        else:
            return {"intent": "help"}
            
    return {"intent": "help"}
