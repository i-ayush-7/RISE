# RISE MCP Server

This is the initial iteration of the Rapid Incident Safety & Escalation (RISE) MCP Server.

## Prerequisites
- Python 3.10+

## Installation

Create a virtual environment and install dependencies:

```bash
# Create the virtual environment
python -m venv venv

# Activate on Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Activate on macOS/Linux (Bash/Zsh):
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Server

Start the server using Python. It will run on `http://127.0.0.1:8000/mcp` using the **Streamable HTTP transport**.

```bash
python server.py
```

## Testing the Server

You can test the server using the provided `test_client.py` script:

```bash
# In a new terminal, with the virtual environment activated:
python test_client.py
```

Output should look like this:
```
Connecting to http://127.0.0.1:8000/mcp...
Connected! Initializing session...
Calling tool 'ping'...
Result: [TextContent(type='text', text='Pong! RISE MCP Server is running.', annotations=None, meta=None)]
```

## Data Model

The server uses a local SQLite database (in `data/rise.db`) to store household emergency information securely. 

The schema includes:
- **households**: Basic family info and address notes.
- **members**: Family members (including pets), ages, support levels, and medical/mobility needs.
- **contacts**: Emergency contacts (e.g., family doctors, out-of-state relatives) with phone numbers and priority.
- **meeting_points**: Safe gathering spots (primary, backup, out-of-area).

To initialize the database with synthetic demo data, run:
```bash
python -m rise.seed
```


## Available Tools (MCP)

This server exposes several tools for any MCP-compliant client (like Claude Desktop) to plan and manage households:

- `list_households`: Lists all registered households.
- `get_household_plan`: Retrieves the full plan (members, contacts, meeting points).
- `list_people_needing_help`: Lists members with mobility/medical needs or who require assistance.
- `add_member` / `update_member`: Manage household members.
- `add_contact` / `update_contact`: Manage emergency contacts.
- `add_meeting_point` / `update_meeting_point`: Manage rally points.
- `get_active_alerts`: Retrieve active alerts for the household area.
- `get_safety_advice`: Get tailored safety instructions and actions based on alerts and the household's unique needs.

## Configuration
You can set the following environment variables:
- `RISE_DB_PATH`: Override the default database path.
- `RISE_ALERT_SOURCE`: The source of alerts. Valid values: `fixture`, `nws`, `nws_recorded` (default: `fixture`).
- `RISE_FIXTURE_SCENARIO`: The active scenario for simulated alerts (e.g. `flood_warning`, `heatwave_warning`, `none`).
- `RISE_NWS_POINT`: Coordinates for NWS alerts when source is `nws` (e.g., `30.7,-86.5`).
- `RISE_NWS_RECORDING`: The name of the recording file when source is `nws_recorded` (e.g., `sample`).

Example with environment variables:
```bash
# Windows PowerShell
$env:RISE_ALERT_SOURCE="nws"
$env:RISE_NWS_POINT="30.7,-86.5"
.\venv\Scripts\python.exe server.py

# Mac/Linux
RISE_ALERT_SOURCE=nws RISE_NWS_POINT=30.7,-86.5 ./venv/bin/python server.py
```

## Check-in and Escalation

RISE includes check-in tools (start_checkin, ecord_checkin, get_checkin_status, close_checkin) to help a household account for its members during an emergency.

**Note**: R.I.S.E. never contacts anyone automatically. The tools create a local tracking record and provide advice on who to contact next. If anyone is in immediate danger, call your local emergency number.

Escalation thresholds are based on elapsed time:
- < 5 minutes: Level 0 (ask to confirm safe)
- 5-9 minutes: Level 1 (call directly)
- 10-19 minutes: Level 2 (escalate to priority 1 contact)
- >= 20 minutes: Level 3 (escalate to priority 2 contact and advise local emergency services)

