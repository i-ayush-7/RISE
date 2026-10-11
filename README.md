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

## Web Interface

Start the backend for frontend (BFF):
```bash
python -m bff
```
Open your browser to `http://127.0.0.1:8080`.

The web interface provides 6 dedicated views:
- **Chat**: Live conversational assistant, situation summary, and hero status photo.
- **Board**: Real-time check-in status, safety meter, and copy-ready escalation messages.
- **Alerts**: Active emergency alerts and tailored safety advice tabs.
- **Plan**: Read-only household roster, emergency contacts, and safe meeting points.
- **Log**: MCP tool activity ledger showing calls, statuses, durations, and payloads.
- **More**: Scenario switcher (floods, storms, heatwaves), demo state reset, and high-contrast / large text toggle.

### Security Note
The web page never holds or receives the backend bearer token. The browser connects only to its own origin (`/api/*`), and the BFF attaches authentication credentials server-side when proxying requests to the MCP server.

### Accessibility & Navigation
- **Skip Link**: Top-of-page "Skip to content" link allows immediate keyboard jumping to main views.
- **Keyboard Navigation**: Standard `Tab` navigation for all interactive controls (minimum 44px touch/click target size).
- **Tabbed Panels**: Arrow keys (`ArrowLeft`, `ArrowRight`) to cycle between tabs on the Alerts view.
- **Screen Reader Announcements**: Live region (`#live-announcer`) announces view changes and dynamic updates.

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


## Security

The MCP server uses a bearer token for authentication to protect sensitive household data and emergency plans. The token prevents unauthorized access from malicious websites or unauthorized local apps. 

**Generating a Token:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Starting the Server Securely:**
PowerShell:
```powershell
$env:RISE_AUTH_TOKEN="YOUR_GENERATED_TOKEN"
python server.py
```

Bash:
```bash
RISE_AUTH_TOKEN="YOUR_GENERATED_TOKEN" python server.py
```

The server binds exclusively to `127.0.0.1` (localhost) by default. If you need to access the server locally without authentication for development, set `RISE_ALLOW_NO_AUTH=1`.

The server also implements Host and Origin header validation to protect against DNS rebinding attacks. You can allow additional hosts by specifying a comma-separated list in `RISE_ALLOWED_HOSTS` and `RISE_ALLOWED_ORIGINS`.

### Public tunnel (optional)
A quick tunnel (for example Cloudflare's) exposes the server publicly over the internet.
If you use a tunnel, the bearer token and `RISE_ALLOWED_HOSTS` must be set to the tunnel's hostname first. The token must be rotated afterwards.
Nothing real should be stored in the household database. Judges can run the project locally without any tunnel.

### Demo Mode
For demonstration purposes, you can enable a simulated clock to test escalations without waiting in real-time.
- Set `RISE_DEMO_MODE=1` and `RISE_DEMO_CLOCK_FILE=/absolute/path/to/clock.txt`.
- The server will read an integer (minutes to advance) from that file and treat the current time as `real + offset`.
- Demo mode is strictly local-only and must NEVER be used with a public tunnel (like Cloudflare) or `RISE_ALLOWED_HOSTS`. Any attempt to expose the server while in demo mode will cause a startup error.
