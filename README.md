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
