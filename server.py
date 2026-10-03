from mcp.server.mcpserver import MCPServer

# Create an MCPServer instance named "rise"
server = MCPServer("rise")

@server.tool()
def ping() -> str:
    """A simple ping tool that returns a confirmation."""
    return "Pong! RISE MCP Server is running."

if __name__ == "__main__":
    # Run using the streamable-http transport on port 8000
    server.run(transport="streamable-http", host="127.0.0.1", port=8000)
