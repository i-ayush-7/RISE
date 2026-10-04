import asyncio
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from rise.tools import (
    list_households,
    get_household_plan,
    list_people_needing_help,
    add_member,
    update_member,
    add_contact,
    update_contact,
    add_meeting_point,
    update_meeting_point
)

server = MCPServer("rise")

@server.tool(annotations=ToolAnnotations(readOnlyHint=True))
def ping() -> str:
    """Check if the RISE MCP server is running."""
    return "pong"

@server.tool(description="List all households. Used to find the household_id if there are multiple.", annotations=ToolAnnotations(readOnlyHint=True))
def tool_list_households() -> list:
    return list_households()

@server.tool(description="Get the full emergency plan for a household, including summary, members, contacts, and meeting points.", annotations=ToolAnnotations(readOnlyHint=True))
def tool_get_household_plan(household_id: int = None) -> dict:
    return get_household_plan(household_id)

@server.tool(description="List members of a household who need assistance, have mobility needs, or medical needs.", annotations=ToolAnnotations(readOnlyHint=True))
def tool_list_people_needing_help(household_id: int = None) -> list:
    return list_people_needing_help(household_id)

@server.tool(description="Add a new member or pet to the household. Enums: age_group (child, adult, senior, pet), support_level (independent, needs_assistance, dependent).")
def tool_add_member(name: str, age_group: str, support_level: str, mobility_needs: str = None, medical_needs: str = None, notes: str = None, is_pet: int = 0, household_id: int = None) -> dict:
    return add_member(name, age_group, support_level, mobility_needs, medical_needs, notes, is_pet, household_id)

@server.tool(description="Update an existing member. Provide only the fields to update as keyword arguments.")
def tool_update_member(member_id: int, updates: dict, household_id: int = None) -> dict:
    return update_member(member_id, updates, household_id)

@server.tool(description="Add an emergency contact.")
def tool_add_contact(name: str, phone: str, relationship: str = None, priority: int = 1, household_id: int = None) -> dict:
    return add_contact(name, phone, relationship, priority, household_id)

@server.tool(description="Update an existing emergency contact. Provide only the fields to update as keyword arguments.")
def tool_update_contact(contact_id: int, updates: dict, household_id: int = None) -> dict:
    return update_contact(contact_id, updates, household_id)

@server.tool(description="Add a meeting point. Enums: kind (primary, backup, out_of_area).")
def tool_add_meeting_point(label: str, kind: str, description: str = None, household_id: int = None) -> dict:
    return add_meeting_point(label, kind, description, household_id)

@server.tool(description="Update an existing meeting point. Provide only the fields to update as keyword arguments.")
def tool_update_meeting_point(mp_id: int, updates: dict, household_id: int = None) -> dict:
    return update_meeting_point(mp_id, updates, household_id)

if __name__ == "__main__":
    server.run(transport="streamable-http", host="127.0.0.1", port=8000)
