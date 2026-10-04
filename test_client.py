import asyncio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import LATEST_PROTOCOL_VERSION

async def run_client():
    url = "http://127.0.0.1:8000/mcp"
    
    print(f"Connecting to {url}...")
    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            print(f"Negotiated Protocol Version: {session.protocol_version}")
            
            tools = await session.list_tools()
            print("\nRegistered Tools:")
            for tool in tools.tools:
                print(f"- {tool.name}: {tool.description}")
            
            print("\nCalling tool_get_household_plan...")
            plan = await session.call_tool("tool_get_household_plan", {})
            print(plan.content[0].text)

            print("\nCalling tool_list_people_needing_help...")
            help_list = await session.call_tool("tool_list_people_needing_help", {})
            print(help_list.content[0].text)

if __name__ == "__main__":
    asyncio.run(run_client())
