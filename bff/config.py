import os
import re
import secrets

def load_config():
    bff_port_str = os.environ.get("RISE_BFF_PORT", "8080")
    try:
        bff_port = int(bff_port_str)
        if not (1024 <= bff_port <= 65535):
            raise ValueError
    except ValueError:
        raise ValueError("RISE_BFF_PORT must be an integer between 1024 and 65535")
        
    mcp_port_str = os.environ.get("RISE_MCP_PORT", "8000")
    try:
        mcp_port = int(mcp_port_str)
    except ValueError:
        raise ValueError("RISE_MCP_PORT must be an integer")
        
    token = os.environ.get("RISE_AUTH_TOKEN", "")
    if len(token) < 32:
        token = secrets.token_urlsafe(32)
        
    nws_point = os.environ.get("RISE_NWS_POINT", "34.0522,-118.2437")
    if not re.match(r"^-?\d+(\.\d+)?,-?\d+(\.\d+)?$", nws_point):
        raise ValueError("RISE_NWS_POINT must be 'lat,lon'")
        
    return {
        "bff_port": bff_port,
        "mcp_port": mcp_port,
        "token": token,
        "nws_point": nws_point,
        "bind_host": "127.0.0.1"
    }

config = load_config()
