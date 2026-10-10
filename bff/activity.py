import threading
import datetime
import json
import copy

class ActivityLog:
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.buffer = []
        self.lock = threading.Lock()
        self.next_id = 1
        
    def add(self, tool: str, arguments: dict, ok: bool, ms: int, result: str):
        with self.lock:
            # truncate result
            if isinstance(result, (dict, list)):
                res_text = json.dumps(result)
            else:
                res_text = str(result)
                
            if len(res_text) > 2000:
                res_text = res_text[:1997] + "..."
                
            entry = {
                "id": self.next_id,
                "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "tool": tool,
                "arguments": copy.deepcopy(arguments),
                "ok": ok,
                "ms": int(ms),
                "result": res_text
            }
            self.next_id += 1
            self.buffer.append(entry)
            if len(self.buffer) > self.capacity:
                self.buffer.pop(0)
                
    def get_since(self, after_id: int):
        with self.lock:
            return [copy.deepcopy(e) for e in self.buffer if e["id"] > after_id]

activity_log = ActivityLog()
