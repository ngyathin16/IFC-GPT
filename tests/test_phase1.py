"""Phase 1 acceptance tests — MCP Server Foundation.

Verifies:
  - ping tool is importable and returns 'pong'
  - server module is importable without a live Blender connection
  - every .py file under src/ and validate/ has a module docstring
"""

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def _collect_py_files(*roots: Path) -> list[Path]:
    """Return all .py files under the given root directories."""
    files: list[Path] = []
    for root in roots:
        files.extend(root.rglob("*.py"))
    return files


# ---------------------------------------------------------------------------
# Ping tool
# ---------------------------------------------------------------------------

class TestPingTool:
    def test_ping_returns_pong(self) -> None:
        """ping() must return the literal string 'pong'."""
        from blender_mcp.mcp_functions.ping import ping  # type: ignore[import]

        result = ping()
        assert result == "pong", f"Expected 'pong', got {result!r}"

    def test_ping_is_registered_as_mcp_tool(self) -> None:
        """ping must be decorated with @mcp.tool() and registered on the FastMCP instance."""
        from blender_mcp.mcp_instance import mcp  # type: ignore[import]

        tool_names = [t.name for t in mcp._tool_manager.list_tools()]
        assert "ping" in tool_names, f"'ping' not found in registered tools: {tool_names}"


# ---------------------------------------------------------------------------
# Server importability (no live Blender required)
# ---------------------------------------------------------------------------

class TestServerImport:
    def test_server_module_importable(self) -> None:
        """blender_mcp.server must import without raising (Blender connection is lazy)."""
        import blender_mcp.server  # type: ignore[import]  # noqa: F401

    def test_mcp_instance_importable(self) -> None:
        """blender_mcp.mcp_instance must expose a FastMCP object named `mcp`."""
        from mcp.server.fastmcp import FastMCP

        from blender_mcp.mcp_instance import mcp  # type: ignore[import]

        assert isinstance(mcp, FastMCP)


# ---------------------------------------------------------------------------
# Module docstrings
# ---------------------------------------------------------------------------

class TestModuleDocstrings:
    @pytest.mark.parametrize(
        "py_file",
        _collect_py_files(SRC_ROOT, PROJECT_ROOT / "validate"),
        ids=lambda p: str(p.relative_to(PROJECT_ROOT)),
    )
    def test_has_module_docstring(self, py_file: Path) -> None:
        """Every .py file under src/ and validate/ must have a module-level docstring."""
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            pytest.fail(f"SyntaxError in {py_file}: {exc}")

        docstring = ast.get_docstring(tree)
        assert docstring, (
            f"Missing module docstring in {py_file.relative_to(PROJECT_ROOT)}"
        )
