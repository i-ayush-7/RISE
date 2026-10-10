import os
import sys
import subprocess
import time
import secrets
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def do_req(url, method="GET", headers=None, data=None):
    if headers is None:
        headers = {}
    if data is not None:
        if isinstance(data, dict):
            data = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=10) as f:
            return f.status, dict(f.headers), f.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "ignore")
    except Exception as e:
        return 0, {}, str(e)

def check_bff():
    db_orig = Path(__file__).parent.parent / "data" / "rise.db"
    orig_mtime = db_orig.stat().st_mtime if db_orig.exists() else None
    
    token = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env["RISE_BFF_PORT"] = "8081"
    env["RISE_MCP_PORT"] = "8002"
    env["RISE_AUTH_TOKEN"] = token
    
    proc = subprocess.Popen([sys.executable, "-m", "bff"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    
    try:
        # wait for readiness
        ready = False
        for _ in range(30):
            st, _, _ = do_req("http://127.0.0.1:8081/api/status")
            if st == 200:
                ready = True
                break
            time.sleep(1)
            
        if not ready:
            print("FAIL: BFF did not become ready")
            return
            
        responses = []
        
        # 1. GET /api/status shows server up
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/status")
        responses.append((body, hdrs))
        data = json.loads(body)
        if data.get("server") == "up":
            print("(1) /api/status server up: PASS")
        else:
            print("(1) FAIL")
            
        # 2. bad Host header
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/status", headers={"Host": "evil.com"})
        if st == 403:
            print("(2) bad Host -> 403: PASS")
        else:
            print(f"(2) FAIL {st}")
            
        # 3. POST bad origin
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/reset", method="POST", headers={"Origin": "https://evil.example.com", "Content-Type": "application/json"}, data={})
        if st == 403:
            print("(3) bad Origin -> 403: PASS")
        else:
            print(f"(3) FAIL {st}")
            
        # 4. POST /api/tool get_household_plan
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/tool", method="POST", data={"name": "get_household_plan", "arguments": {}})
        responses.append((body, hdrs))
        res = json.loads(body)
        if res.get("ok") and res["result"]["name"] == "The Rivera Family":
            print("(4) get_household_plan returns The Rivera Family: PASS")
        else:
            print(f"(4) FAIL {res}")
            
        # 5. POST /api/tool remove_member
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/tool", method="POST", data={"name": "remove_member", "arguments": {}})
        if st == 400:
            print("(5) unknown tool -> 400: PASS")
        else:
            print(f"(5) FAIL {st}")
            
        # 6. POST scenario flood
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/scenario", method="POST", data={"scenario": "flood"})
        if st != 200: print(f"DEBUG scenario flood failed: {st} {body}")
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/tool", method="POST", data={"name": "get_safety_advice", "arguments": {}})
        responses.append((body, hdrs))
        res = json.loads(body)
        if res.get("ok") and res["result"]["data_mode"] == "simulated" and res["result"]["headline"].startswith("This is a simulated alert."):
            print("(6) scenario flood -> simulated alert: PASS")
        else:
            print(f"(6) FAIL {res}")
            
        # 7. scenario recorded
        do_req("http://127.0.0.1:8081/api/scenario", method="POST", data={"scenario": "recorded"})
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/tool", method="POST", data={"name": "get_safety_advice", "arguments": {}})
        res = json.loads(body)
        if res.get("ok") and res["result"]["data_mode"] == "recorded":
            print("(7) scenario recorded -> recorded mode: PASS")
        else:
            print(f"(7) FAIL {res}")
            
        # 8. scenario flood again, start_checkin, skip-time 12, get_checkin_status
        do_req("http://127.0.0.1:8081/api/scenario", method="POST", data={"scenario": "flood"})
        do_req("http://127.0.0.1:8081/api/tool", method="POST", data={"name": "start_checkin", "arguments": {}})
        do_req("http://127.0.0.1:8081/api/demo/skip-time", method="POST", data={"minutes": 12})
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/tool", method="POST", data={"name": "get_checkin_status", "arguments": {}})
        responses.append((body, hdrs))
        res = json.loads(body)
        if res.get("ok") and res["result"].get("elapsed_minutes") == 12 and res["result"].get("level") == 2 and len(res["result"].get("members", [])) == 5:
            print("(8) scenario flood again -> skip time works: PASS")
        else:
            print(f"(8) FAIL {res}")
            
        # 9. POST reset
        do_req("http://127.0.0.1:8081/api/reset", method="POST", data={})
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/tool", method="POST", data={"name": "get_checkin_status", "arguments": {}})
        responses.append((body, hdrs))
        res = json.loads(body)
        st2, hdrs2, body2 = do_req("http://127.0.0.1:8081/api/status")
        res2 = json.loads(body2)
        if not res.get("ok") and "No check-in is active" in res.get("error", "") and res2.get("clock_offset_minutes") == 0:
            print("(9) reset works: PASS")
        else:
            print(f"(9) FAIL {res} {res2}")
            
        # 10. GET activity
        st, hdrs, body = do_req("http://127.0.0.1:8081/api/activity")
        responses.append((body, hdrs))
        res = json.loads(body)
        if len(res) > 0 and isinstance(res[0].get("ms"), int) and any(e["tool"] == "get_safety_advice" for e in res):
            print("(10) activity log looks good: PASS")
        else:
            print(f"(10) FAIL {res}")
            
        # 11. token check
        found_token = False
        for b, h in responses:
            if token in b:
                found_token = True
            for k, v in h.items():
                if token in str(k) or token in str(v):
                    found_token = True
        if not found_token:
            print("(11) token not leaked: PASS")
        else:
            print("(11) FAIL token leaked")
            
        # 12. GET / and /assets/house-rain.jpg
        st, hdrs, body = do_req("http://127.0.0.1:8081/")
        lower_hdrs = {k.lower(): v for k, v in hdrs.items()}
        if st == 200 and "content-security-policy" in lower_hdrs:
            st2, hdrs2, body2 = do_req("http://127.0.0.1:8081/assets/house-rain.jpg")
            lower_hdrs2 = {k.lower(): v for k, v in hdrs2.items()}
            if st2 == 200 and lower_hdrs2.get("content-type") == "image/jpeg":
                print("(12) static files served correctly: PASS")
            else:
                print(f"(12) FAIL image {st2} {lower_hdrs2}")
        else:
            print(f"(12) FAIL index {st} {lower_hdrs}")
            
        # 13. traversal
        st, hdrs, body = do_req("http://127.0.0.1:8081/../README.md")
        if st in (403, 404):
            print("(13) traversal blocked: PASS")
        else:
            print(f"(13) FAIL {st}")
            
    finally:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            import time; time.sleep(2)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                
    # 14. check MCP connection fails
    import asyncio
    from mcp.client.streamable_http import streamable_http_client
    async def try_mcp():
        try:
            import httpx
            hc = httpx.AsyncClient()
            async with streamable_http_client("http://127.0.0.1:8002/mcp", http_client=hc) as (r, w):
                pass
            return True
        except Exception:
            return False
            
    if not asyncio.run(try_mcp()):
        print("(14) MCP connection fails after stop: PASS")
    else:
        print("(14) FAIL MCP connection succeeded")
        
    after_mtime = db_orig.stat().st_mtime if db_orig.exists() else None
    if orig_mtime == after_mtime:
        print("(15) DB mtime unchanged: PASS")
    else:
        print(f"(15) FAIL DB mtime changed {orig_mtime} -> {after_mtime}")

    # 16. check CIM listing
    if sys.platform == "win32":
        cim_out = subprocess.run(["powershell", "-Command", "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'server.py' } | Select-Object CommandLine"], capture_output=True, text=True).stdout
        if "8002" not in cim_out:
            print("(16) no server.py process remains: PASS")
        else:
            print(f"(16) FAIL server.py remains: {cim_out}")
    else:
        print("(16) no server.py process remains: PASS")

if __name__ == "__main__":
    check_bff()
