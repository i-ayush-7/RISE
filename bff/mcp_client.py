import json
import asyncio
from typing import Tuple, Any, Optional
from bff.config import config

TOOL_ALLOWLIST = {
    "ping", "list_households", "get_household_plan", "list_people_needing_help",
    "get_active_alerts", "get_safety_advice", "start_checkin", "record_checkin",
    "get_checkin_status", "close_checkin", "add_member", "update_member",
    "add_contact", "update_contact", "add_meeting_point", "update_meeting_point"
}

def get_http_client():
    import httpx2
    return httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {config['token']}"} if config["token"] else {}
    )

async def status() -> Optional[str]:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    url = f"http://127.0.0.1:{config['mcp_port']}/mcp"
    try:
        http_client = get_http_client()
        result = None
        try:
            async with asyncio.timeout(15):
                async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        init_res = await session.initialize()
                        result = getattr(init_res, "protocol_version", getattr(init_res, "protocolVersion", None))
        except Exception as e:
            if "unhandled errors in a TaskGroup" in str(e) and result is not None:
                pass
            else:
                return None
        return result
    except Exception:
        return None
    finally:
        if 'http_client' in locals():
            await http_client.aclose()

async def call_tool(name: str, arguments: dict) -> Tuple[bool, Any, Optional[str]]:
    if name not in TOOL_ALLOWLIST:
        return False, f"Tool {name} not in allowlist", None
        
    if not isinstance(arguments, dict):
        return False, "Arguments must be a JSON object", None
        
    if len(arguments) > 20:
        return False, "Too many arguments (max 20)", None
        
    for k, v in arguments.items():
        if isinstance(v, str) and len(v) > 1000:
            return False, f"Argument {k} too long (max 1000 characters)", None
            
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    url = f"http://127.0.0.1:{config['mcp_port']}/mcp"
    try:
        http_client = get_http_client()
        result = None
        try:
            async with asyncio.timeout(15):
                async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        init_res = await session.initialize()
                        proto = getattr(init_res, "protocol_version", getattr(init_res, "protocolVersion", None))
                        
                        res = await session.call_tool(name, arguments)
                        text = res.content[0].text
                        
                        if getattr(res, "is_error", getattr(res, "isError", False)):
                            result = (False, text, proto)
                        else:
                            try:
                                payload = json.loads(text)
                            except Exception:
                                payload = text
                            result = (True, payload, proto)
        except Exception as e:
            if "unhandled errors in a TaskGroup" in str(e) and result is not None:
                pass
            else:
                return False, str(e), None
                
        return result
    except Exception as e:
        return False, str(e), None
    finally:
        if 'http_client' in locals():
            await http_client.aclose()
