import asyncio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import LATEST_PROTOCOL_VERSION

async def test_ping():
    url = "http://127.0.0.1:8000/mcp"
    
    print(f"Connecting to {url}...")
    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("Connected! Initializing session...")
            init_result = await session.initialize()
            
            print(f"SDK Latest Protocol Version: {LATEST_PROTOCOL_VERSION}")
            print(f"Server Negotiated Protocol Version: {init_result.protocol_version}")
            
            print("Calling tool 'ping'...")
            result = await session.call_tool("ping", {})
            print(f"Result: {result.content}")

if __name__ == "__main__":
    asyncio.run(test_ping())
