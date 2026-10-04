import asyncio
import json
import os
import sys
import shutil
import tempfile
import subprocess
import time
from pathlib import Path
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import LATEST_PROTOCOL_VERSION

async def run_client():
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test_rise.db"
    
    env = os.environ.copy()
    env["RISE_DB_PATH"] = str(temp_db_path)
    
    # Seed
    subprocess.run([sys.executable, "-m", "rise.seed"], env=env, check=True, capture_output=True)
    
    # Start server
    server_proc = subprocess.Popen([sys.executable, "server.py"], env=env)
    
    # Wait for server to be ready
    await asyncio.sleep(2)
    
    url = "http://127.0.0.1:8000/mcp"
    
    try:
        print(f"Connecting to {url}...")
        async with streamable_http_client(url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                print(f"Negotiated Protocol Version: {session.protocol_version}")
                
                tools = await session.list_tools()
                print("\nRegistered Tools:")
                for tool in tools.tools:
                    print(f"- {tool.name}: {tool.description}")
                
                print("\nCalling get_household_plan...")
                plan = await session.call_tool("get_household_plan", {})
                for block in plan.content:
                    print(block.text)

                print("\nCalling get_active_alerts...")
                alerts = await session.call_tool("get_active_alerts", {})
                for block in alerts.content:
                    print(block.text)

                print("\nCalling get_safety_advice...")
                advice = await session.call_tool("get_safety_advice", {})
                for block in advice.content:
                    print(block.text)

                print("\nCalling list_people_needing_help...")
                help_list = await session.call_tool("list_people_needing_help", {})
                for block in help_list.content:
                    print(block.text)

                print("\nCalling add_member with invalid age_group...")
                try:
                    invalid_member = await session.call_tool("add_member", {
                        "name": "Invalid Member",
                        "age_group": "ghost",
                        "support_level": "independent"
                    })
                    if invalid_member.is_error:
                        print("Error from server:")
                    for block in invalid_member.content:
                        print(block.text)
                except Exception as e:
                    print(f"Exception from server: {e}")

                print("\nCalling update_member with missing member_id 9999...")
                try:
                    missing_member = await session.call_tool("update_member", {
                        "member_id": 9999,
                        "name": "Ghost"
                    })
                    if missing_member.is_error:
                        print("Error from server:")
                    for block in missing_member.content:
                        print(block.text)
                except Exception as e:
                    print(f"Exception from server: {e}")

                print("\n--- Check-in Sequence ---")
                print("1. Starting check-in...")
                res1 = await session.call_tool("start_checkin", {"reason": "Simulated flood drill"})
                for block in res1.content:
                    print(block.text)
                    
                print("\n2. Recording Maria as safe...")
                res2 = await session.call_tool("record_checkin", {"member_name": "Maria", "status": "safe"})
                for block in res2.content:
                    print(block.text)
                    
                print("\n3. Recording Carlos as safe...")
                res3 = await session.call_tool("record_checkin", {"member_name": "Carlos", "status": "safe"})
                for block in res3.content:
                    print(block.text)
                    
                print("\n4. Getting check-in status...")
                res4 = await session.call_tool("get_checkin_status", {})
                for block in res4.content:
                    print(block.text)
                    
                print("\n5. Closing check-in...")
                res5 = await session.call_tool("close_checkin", {})
                for block in res5.content:
                    print(block.text)

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(run_client())
