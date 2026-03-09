"""Ping tool for MCP server health-check.

Provides a single `ping` tool that returns a pong response, allowing any MCP
client (e.g. Cursor, MCP Inspector) to verify the server is alive without
requiring a live Blender connection.
"""

from ..mcp_instance import mcp


@mcp.tool()
def ping() -> str:
    """Health-check tool — returns 'pong' to confirm the MCP server is running.

    Returns:
        str: The literal string "pong".
    """
    return "pong"
