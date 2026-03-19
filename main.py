"""IFC-GPT entry point.

Usage:
    uv run main.py               # MCP stdio server (Windsurf/Claude Desktop)
    uv run main.py --http        # FastAPI HTTP server (web frontend)
    uv run main.py --http --port 8000
"""
import sys


def main():
    if "--http" in sys.argv:
        import uvicorn
        port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000
        uvicorn.run("api.server:app", host="0.0.0.0", port=port, reload=True)
    else:
        from blender_mcp.server import main as server_main
        server_main()


if __name__ == "__main__":
    main()
