# Friction log: R.I.S.E.

Amazon Developer Hackathon, Alexa+ track. This log records real obstacles hit while building
a self-hosted MCP server (Streamable HTTP) and its web front end.

**Environment:** Windows, Python 3.13, MCP Python SDK 2.3.0, protocol version negotiated
2025-11-25, U.S. National Weather Service API.

## Summary

| # | Area | Issue | Severity |
|---|---|---|---|
| 1 | MCP Python SDK | `FastMCP` renamed to `MCPServer` in 2.x; examples use the old name | Medium |
| 2 | MCP Python SDK | Tool exceptions reach the client only as a generic message | Medium |
| 3 | MCP Python SDK | No obvious way to send an `Authorization` header from the client | Medium |
| 4 | MCP Python SDK | TaskGroup error when closing a client session after a successful call | Medium |
| 5 | MCP spec and SDK | Unclear which protocol version to target | Low |
| 6 | Windows tooling | Stopping a child server left its child process running | Medium |
| 7 | Alexa+ track | No documented way to test a custom MCP server with Alexa+ | High |

---

## 1. Starting a server with the current MCP Python SDK

- **Task attempted:** Create a minimal MCP server with one tool over Streamable HTTP.
- **Steps taken:** Installed the SDK and used the documented `FastMCP` import from examples.
- **Expected:** The example runs as written.
- **Actual:** In SDK 2.x the high-level class is `MCPServer` in a different module, so the
  old import failed.
- **Severity:** Medium.
- **Workaround:** Inspected the installed package to find the new class and the `run()` options.
- **Suggestion:** Add a prominent migration note and update the examples and docs.

## 2. Showing a validation error to the calling assistant

- **Task attempted:** Return a readable error such as "age_group must be one of ..." to the client.
- **Steps taken:** Raised `ValueError` inside a tool.
- **Expected:** The message reaches the client.
- **Actual:** The client received only a generic "Error executing tool ..." message; the
  original text stays on the server.
- **Severity:** Medium.
- **Workaround:** Raised the SDK's `ToolError` for user-safe messages, and kept database and
  unexpected errors generic. Found by reading the SDK source.
- **Suggestion:** Document this clearly and consider an opt-in to surface messages.

## 3. Calling my own server from my backend with a bearer token

- **Task attempted:** Connect to my server over Streamable HTTP with an `Authorization` header.
- **Steps taken:** Used the Streamable HTTP client from the SDK.
- **Expected:** A documented way to pass a custom header.
- **Actual:** I had to read the client source to learn that it accepts a custom HTTP client.
- **Severity:** Medium.
- **Workaround:** Passed an `httpx2` client configured with the header.
- **Suggestion:** Add an authenticated-client example to the docs.

## 4. Closing a client session after a successful call

- **Task attempted:** Call a tool and exit the client context manager cleanly.
- **Steps taken:** Called a tool inside the client context managers.
- **Expected:** Clean exit.
- **Actual:** A TaskGroup error was raised on close even though the call had succeeded.
- **Severity:** Medium.
- **Workaround:** Kept the result and ignored that specific error after success.
- **Suggestion:** Fix the cleanup or document the behavior.

## 5. Choosing the protocol version to target

- **Task attempted:** Make sure the server meets "spec 2025-11-25 or later".
- **Steps taken:** Read the rules, then printed the SDK's latest protocol constant and the
  version negotiated with my server.
- **Expected:** One clear target.
- **Actual:** The SDK's latest constant is newer (2026-07-28) while the connection negotiated
  2025-11-25.
- **Severity:** Low.
- **Workaround:** Verified the negotiated version at runtime and added it to my checks.
- **Suggestion:** State in the track docs which version to target and how to confirm it.

## 6. Stopping my server cleanly on Windows

- **Task attempted:** Start the MCP server as a child process of my web backend and stop it
  on shutdown.
- **Steps taken:** Terminated the child process.
- **Expected:** The port closes.
- **Actual:** The virtual-environment launcher left a second process running the server on
  its port, so the next start failed or answered from a stale server.
- **Severity:** Medium.
- **Workaround:** Started the child in its own process group, stopped the whole process tree
  with `taskkill /T`, and checked that the ports were really closed.
- **Suggestion:** Document process handling for Windows developers.

## 7. Testing my MCP server with Alexa+

- **Task attempted:** Try my server with Alexa+.
- **Steps taken:** Read the track description and the resources page.
- **Expected:** A way to connect a custom MCP server, and its authentication requirements.
- **Actual:** I found no test path and no documentation of how Alexa+ authenticates to a
  self-hosted server.
- **Severity:** High.
- **Workaround:** Simulated the assistant side with a web chat and a rules-based parser, and
  said so plainly in the README and demo.
- **Suggestion:** Publish a simulator or sandbox and document the authentication model.
