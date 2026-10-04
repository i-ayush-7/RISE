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
            
            print("\nCalling get_household_plan...")
            plan = await session.call_tool("get_household_plan", {})
            for block in plan.content:
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
                for block in invalid_member.content:
                    print(block.text)
            except Exception as e:
                print(f"Error from server: {e}")

if __name__ == "__main__":
    asyncio.run(run_client())
