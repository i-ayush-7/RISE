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
