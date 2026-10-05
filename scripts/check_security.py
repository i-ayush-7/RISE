import asyncio
import os
import sys
import shutil
import tempfile
import subprocess
import time
import urllib.request
import urllib.error
import secrets
from pathlib import Path

def raw_check(url, headers):
    req = urllib.request.Request(url, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return -1

async def check_security():
    db_orig = Path(__file__).parent.parent / "data" / "rise.db"
    orig_mtime = db_orig.stat().st_mtime if db_orig.exists() else None
    
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test_rise.db"
    if db_orig.exists():
        shutil.copy2(db_orig, temp_db_path)
    
    token = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env["RISE_DB_PATH"] = str(temp_db_path)
    env["RISE_AUTH_TOKEN"] = token
    
    # Seed temp db if not exists
    if not temp_db_path.exists():
        subprocess.run([sys.executable, "-m", "rise.seed"], env=env, check=True)
        
    server_proc = subprocess.Popen([sys.executable, "server.py"], env=env, stdout=subprocess.DEVNULL)
    time.sleep(2)
    
    url = "http://127.0.0.1:8000/mcp"
    
    print("--- Security Checks ---")
    
    # a. No token
    st = raw_check(url, {})
    if st == 401:
        print("(a) No token -> 401: PASS")
    else:
        print(f"(a) No token -> {st}: FAIL")
        
    # b. Wrong token
    st = raw_check(url, {"Authorization": "Bearer wrongtoken"})
    if st == 401:
        print("(b) Wrong token -> 401: PASS")
    else:
        print(f"(b) Wrong token -> {st}: FAIL")
        
    # c. Wrong Host
    st = raw_check(url, {"Host": "evil.example.com", "Authorization": f"Bearer {token}"})
    if st == 403:
        print("(c) Wrong Host -> 403: PASS")
    else:
        print(f"(c) Wrong Host -> {st}: FAIL")
        
    # d. Correct token with MCP client
    print("(d) The correct token:")
    try:
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        import httpx2
        http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"})
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                init_res = await session.initialize()
                print("    Initialize: PASS")
                print(f"    Protocol version negotiated: {init_res.protocol_version}")
                
                tools_res = await session.list_tools()
                if any(t.name == "get_household_plan" for t in tools_res.tools):
                    print("    list_tools: PASS")
                else:
                    print("    list_tools: FAIL")
                    
                plan_res = await session.call_tool("get_household_plan", {"household_id": 1})
                if "The Rivera Family" in plan_res.content[0].text:
                    print("    get_household_plan: PASS")
                else:
                    print("    get_household_plan: FAIL")
    except Exception as e:
        import traceback
        print("    FAIL")
        traceback.print_exc()
        
    server_proc.terminate()
    server_proc.wait(timeout=2)
    shutil.rmtree(temp_dir)
    
    after_mtime = db_orig.stat().st_mtime if db_orig.exists() else None
    print(f"\ndata/rise.db unchanged: {orig_mtime == after_mtime}")

if __name__ == "__main__":
    asyncio.run(check_security())
