# R.I.S.E. (Rapid Incident Safety & Escalation)

A household emergency copilot that never guesses. R.I.S.E. is a self-hosted
[MCP](https://modelcontextprotocol.io) server (Streamable HTTP) that an assistant such as
Alexa+ can call during a flood, heatwave or other alert, plus a web front end that
simulates the assistant side.

Built for the Amazon Developer Hackathon, **Alexa+ track**.

> **Honest scope:** Alexa+ itself is *simulated* by a web chat with a rules-based parser.
> The MCP server, its tools, the safety rules and the security layer are real.
> The flood and heatwave drills are fixtures. NWS data covers the U.S. only.

## What it does

When a warning arrives, a family has to remember who needs extra help, who to call first and
where to meet. R.I.S.E. keeps that plan and answers from it:

- **Household plan:** people, pets, needs, contacts and meeting points (SQLite, validated).
- **Alerts:** a simulated drill, a recorded real NWS warning, or live NWS data.
  Every alert is labeled with its data mode.
- **Advice:** a ranked action list from fixed rules, with the alert's official instructions
  copied word for word.
- **Family check-in:** records who has confirmed they are safe, escalates at 5, 10 and 20
  minutes (demo thresholds) from asking, to calling directly, to contacting your emergency
  contact, and drafts a message you can copy.

**R.I.S.E. never contacts anyone.** It tells you who to call.

## Quick start (about 2 minutes)

Developed and tested on Windows with Python 3.13. Other platforms are untested.

```powershell
git clone https://github.com/i-ayush-7/RISE.git
cd RISE
python -m venv venv
.\venv\Scripts\Activate.ps1        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python -m bff
```

Open **http://127.0.0.1:8080**. The command starts everything: the web page, a backend
that acts as an MCP client, and the MCP server on a throwaway copy of the demo database.
Press Ctrl+C to stop; the child server is stopped with it.

Try: **More > Flood drill**, then in Chat: `What should we do?`, `Start a check-in`,
`Maria is safe`, `Elena fell and cannot stand`, and on the Board press **Skip time +5 min**
to see escalation.

## Run the tests

```powershell
python -m unittest discover tests
python scripts\check_bff.py        # end-to-end checks; starts and stops its own servers
```

## Use the MCP server on its own

```powershell
python -m rise.seed                # creates data/rise.db with a fictional household
$env:RISE_AUTH_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
python server.py                   # http://127.0.0.1:8000/mcp  (Streamable HTTP)
```

Every request needs `Authorization: Bearer <token>`. The server refuses to start without a
token of at least 32 characters. `test_client.py` is a minimal client. The connection
negotiates protocol version 2025-11-25.

### Tools (16)

| Group | Tools |
|---|---|
| Health | `ping` |
| Plan (read) | `list_households`, `get_household_plan`, `list_people_needing_help` |
| Plan (write) | `add_member`, `update_member`, `add_contact`, `update_contact`, `add_meeting_point`, `update_meeting_point` |
| Alerts and advice | `get_active_alerts`, `get_safety_advice` |
| Check-in | `start_checkin`, `record_checkin`, `get_checkin_status`, `close_checkin` |

There are deliberately **no delete tools**.

## How it works

```
Browser (web/)  ->  BFF (bff/, 127.0.0.1:8080)  ->  MCP server (server.py, 127.0.0.1:8000/mcp)
 no token           holds the token, MCP client       tools, rules, SQLite, alert providers
```

- `rise/` holds the data layer, the pure advice and escalation engines, and the alert providers.
- `bff/` is the web backend, the tool allowlist, the chat intent parser and the process manager.
- `web/` is plain HTML, CSS and JavaScript modules with no build step.

## Safety design

- Someone is marked safe only when a person says so plainly. Questions, hedges, negations,
  conditionals and mixed statements record nothing and get a clarifying reply.
- "Everyone is confirmed safe" appears only when the server says every person and pet is.
- If alerts cannot be checked, the app says so; it never shows "no alerts".
- Alert and note text is displayed as data, never treated as instructions.
- Medical details never go into draft messages.

## Data modes and configuration

| Variable | Purpose |
|---|---|
| `RISE_ALERT_SOURCE` | `fixture` (default), `nws_recorded`, or `nws` (live, U.S. only) |
| `RISE_FIXTURE_SCENARIO` | `flood_warning`, `heatwave_warning`, `none` |
| `RISE_NWS_RECORDING` | recording name (default `sample`, a real past NWS warning) |
| `RISE_NWS_POINT` | `lat,lon` for live NWS alerts |
| `RISE_CONTACT` | contact string sent in the NWS User-Agent header (optional) |
| `RISE_DB_PATH` | database file (default `data/rise.db`) |
| `RISE_AUTH_TOKEN` | bearer token for the MCP server (32+ characters) |
| `RISE_ALLOWED_HOSTS`, `RISE_ALLOWED_ORIGINS` | extra Host and Origin allowlist entries |
| `RISE_ALLOW_NO_AUTH` | `1` disables the token for local development only |
| `RISE_DEMO_MODE`, `RISE_DEMO_CLOCK_FILE` | simulated clock for demos (local only) |
| `RISE_BFF_PORT`, `RISE_MCP_PORT` | ports (defaults 8080 and 8000) |

## Security notes

Bearer-token authentication, Host and Origin checks, request size limits, localhost-only
binding, strict Content-Security-Policy on the web page, and the token is never sent to the
browser. Demo mode is refused when any non-local host is allowed. **Do not expose the web
interface or demo mode through a public tunnel.** This project has not had a professional
security review.

## Limitations

- Alexa+ is simulated; nothing here has been tested against the real service.
- Chat understanding is rule-based and intentionally conservative.
- Escalation timings are demo defaults, not official guidance.
- Live alerts cover the United States only (National Weather Service).
- General preparedness guidance only; not medical or emergency-services advice. If anyone is
  in danger, call your local emergency number.
- Plan editing is available through MCP tools but not yet in the web interface.

## Credits and license

MIT License (see `LICENSE`). Alert data from the U.S. National Weather Service (weather.gov).
Hero image: artwork supplied by the author. Built with AI coding agents
(Antigravity) that the author directed and reviewed.
