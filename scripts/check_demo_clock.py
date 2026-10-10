import asyncio
import os
import sys
import shutil
import tempfile
import subprocess
import time
import secrets
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def check_demo_clock():
    db_orig = Path(__file__).parent.parent / "data" / "rise.db"
    orig_mtime = db_orig.stat().st_mtime if db_orig.exists() else None
    
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test_rise.db"
    temp_clock_path = Path(temp_dir) / "clock.txt"
    
    token = secrets.token_urlsafe(32)
    
    def setup_env():
        env = os.environ.copy()
        env["RISE_DB_PATH"] = str(temp_db_path)
        env["RISE_AUTH_TOKEN"] = token
        return env
        
    def reset_db():
        if temp_db_path.exists():
            temp_db_path.unlink()
        subprocess.run([sys.executable, "-m", "rise.seed"], env=setup_env(), check=True)
        
    url = "http://127.0.0.1:8000/mcp"
    
    print("--- Demo Clock Checks ---")
    
    # a) with RISE_DEMO_MODE=1 and clock file "0"
    reset_db()
    temp_clock_path.write_text("0", encoding="utf-8")
    env_a = setup_env()
    env_a["RISE_DEMO_MODE"] = "1"
    env_a["RISE_DEMO_CLOCK_FILE"] = str(temp_clock_path)
    
    proc_a = subprocess.Popen([sys.executable, "server.py"], env=env_a, stdout=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        import httpx2
        http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"})
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                await session.call_tool("start_checkin", {})
                res = await session.call_tool("get_checkin_status", {})
                import json
                st = json.loads(res.content[0].text)
                if st.get("elapsed_minutes") == 0 and st.get("level") == 0 and len(st.get("members", [])) == 5:
                    print("(a) clock file 0 -> elapsed_minutes 0, level 0, 5 members: PASS")
                else:
                    print(f"(a) clock file 0 -> FAIL (got {st})")
                    
                # b) write "12" to the clock file
                temp_clock_path.write_text("12", encoding="utf-8")
                res = await session.call_tool("get_checkin_status", {})
                st = json.loads(res.content[0].text)
                if st.get("elapsed_minutes") == 12 and st.get("level") == 2:
                    print("(b) clock file 12 -> elapsed_minutes 12, level 2: PASS")
                else:
                    print(f"(b) clock file 12 -> FAIL (got {st})")
    except Exception as e:
        print(f"FAIL in (a) or (b): {e}")
    finally:
        proc_a.terminate()
        proc_a.wait(timeout=2)
        
    # c) restart the server with fresh db and RISE_DEMO_MODE unset but clock file still "12"
    reset_db()
    env_c = setup_env()
    if "RISE_DEMO_MODE" in env_c:
        del env_c["RISE_DEMO_MODE"]
    env_c["RISE_DEMO_CLOCK_FILE"] = str(temp_clock_path)
    
    proc_c = subprocess.Popen([sys.executable, "server.py"], env=env_c, stdout=subprocess.DEVNULL)
    time.sleep(2)
    try:
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                await session.call_tool("start_checkin", {})
                res = await session.call_tool("get_checkin_status", {})
                import json
                st = json.loads(res.content[0].text)
                if st.get("elapsed_minutes") == 0:
                    print("(c) DEMO_MODE unset -> elapsed_minutes 0 (ignored): PASS")
                else:
                    print(f"(c) DEMO_MODE unset -> FAIL (got {st})")
    except Exception as e:
        print(f"FAIL in (c): {e}")
    finally:
        proc_c.terminate()
        proc_c.wait(timeout=2)
        
    # d) starting server.py with RISE_DEMO_MODE=1 and RISE_ALLOWED_HOSTS=example.com exits with code 2
    env_d = setup_env()
    env_d["RISE_DEMO_MODE"] = "1"
    env_d["RISE_DEMO_CLOCK_FILE"] = str(temp_clock_path)
    env_d["RISE_ALLOWED_HOSTS"] = "example.com"
    proc_d = subprocess.Popen([sys.executable, "server.py"], env=env_d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc_d.wait()
    if proc_d.returncode == 2:
        print("(d) RISE_ALLOWED_HOSTS with demo mode -> exits 2: PASS")
    else:
        print(f"(d) RISE_ALLOWED_HOSTS with demo mode -> FAIL (exited {proc_d.returncode})")
        
    shutil.rmtree(temp_dir)
    after_mtime = db_orig.stat().st_mtime if db_orig.exists() else None
    print(f"\ndata/rise.db modified time before: {orig_mtime}")
    print(f"data/rise.db modified time after:  {after_mtime}")

if __name__ == "__main__":
    asyncio.run(check_demo_clock())
