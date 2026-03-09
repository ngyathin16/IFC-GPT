"""Shared FastMCP singleton used across all blender_mcp modules.

Import `mcp` from here to register tools, resources, and prompts without
creating duplicate server instances.
"""
from mcp.server.fastmcp import FastMCP

mcp: FastMCP = FastMCP(
    "BlenderMCP",
    instructions="Blender integration through the Model Context Protocol",
)