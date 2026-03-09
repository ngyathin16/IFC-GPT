"""Phase 4 acceptance tests — LangGraph Orchestration.

Verifies:
  - agent/graph.py imports cleanly and compiles a valid StateGraph
  - AgentState TypedDict has all required keys
  - Tool governance lists are non-empty and contain expected tools
  - should_repair routing logic (repair vs. export)
  - agent/repair.py: classify_error, build_repair_prompt, repair_node
  - Every .py file in agent/ has a module docstring
  - present_and_export writes a JSON report to reports/
  - Graph nodes are importable and callable (smoke test with minimal state)
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "agent"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_py_files(*roots: Path) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        files.extend(root.rglob("*.py"))
    return files


def _has_module_docstring(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return (
        isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ) if tree.body else False


def _minimal_state(**overrides: Any) -> Dict[str, Any]:
    """Return a minimal AgentState-compatible dict."""
    base: Dict[str, Any] = {
        "messages": [],
        "building_plan": {},
        "tool_calls_log": [],
        "validation_results": {},
        "repair_attempts": 0,
        "final_ifc_path": "",
        "ids_report_path": "",
        "scene_overview": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 4.1 — Graph structure
# ---------------------------------------------------------------------------


class TestGraphImport:
    def test_graph_module_importable(self) -> None:
        from agent import graph  # noqa: F401

    def test_app_is_compiled(self) -> None:
        from agent.graph import app

        assert app is not None

    def test_agent_state_has_required_keys(self) -> None:
        from agent.graph import AgentState

        annotations = AgentState.__annotations__
        required = {
            "messages",
            "building_plan",
            "tool_calls_log",
            "validation_results",
            "repair_attempts",
            "final_ifc_path",
            "ids_report_path",
            "scene_overview",
        }
        for key in required:
            assert key in annotations, f"AgentState missing key: {key}"

    def test_graph_nodes_exist(self) -> None:
        from agent.graph import workflow

        node_names = set(workflow.nodes.keys())
        for expected in {"intake", "plan", "build", "validate", "repair", "export"}:
            assert expected in node_names, f"Graph missing node: {expected}"


# ---------------------------------------------------------------------------
# 4.2 — Tool governance
# ---------------------------------------------------------------------------


class TestToolGovernance:
    def test_plan_tools_non_empty(self) -> None:
        from agent.graph import PLAN_TOOLS

        assert len(PLAN_TOOLS) > 0

    def test_build_tools_contains_create_wall(self) -> None:
        from agent.graph import BUILD_TOOLS

        assert "create_wall" in BUILD_TOOLS or "create_two_point_wall" in BUILD_TOOLS

    def test_validate_tools_read_only(self) -> None:
        from agent.graph import VALIDATE_TOOLS

        for tool in VALIDATE_TOOLS:
            assert tool.startswith("get_") or tool.startswith("capture_"), (
                f"VALIDATE_TOOLS should only contain read-only tools, found: {tool}"
            )

    def test_repair_tools_superset_of_build(self) -> None:
        from agent.graph import BUILD_TOOLS, REPAIR_TOOLS

        for tool in BUILD_TOOLS:
            assert tool in REPAIR_TOOLS, f"REPAIR_TOOLS missing build tool: {tool}"

    def test_repair_tools_includes_update_tools(self) -> None:
        from agent.graph import REPAIR_TOOLS

        update_tools = [t for t in REPAIR_TOOLS if t.startswith("update_")]
        assert len(update_tools) > 0

    def test_execute_blender_code_not_in_build_tools(self) -> None:
        from agent.graph import BUILD_TOOLS

        assert "execute_blender_code" not in BUILD_TOOLS


# ---------------------------------------------------------------------------
# 4.3 — should_repair routing
# ---------------------------------------------------------------------------


class TestShouldRepair:
    def test_routes_to_export_when_valid(self) -> None:
        from agent.graph import should_repair

        state = _minimal_state(
            validation_results={
                "valid": True,
                "schema": {"valid": True},
                "ids": {"valid": True},
                "semantic": {"valid": True},
            }
        )
        assert should_repair(state) == "export"  # type: ignore[arg-type]

    def test_routes_to_repair_when_schema_invalid(self) -> None:
        from agent.graph import should_repair

        state = _minimal_state(
            repair_attempts=0,
            validation_results={
                "valid": False,
                "schema": {"valid": False, "error_count": 1},
                "ids": {"valid": True, "failed": 0},
                "semantic": {"valid": True, "error_count": 0},
            },
        )
        assert should_repair(state) == "repair"  # type: ignore[arg-type]

    def test_routes_to_repair_when_semantic_invalid(self) -> None:
        from agent.graph import should_repair

        state = _minimal_state(
            repair_attempts=1,
            validation_results={
                "valid": False,
                "schema": {"valid": True, "error_count": 0},
                "ids": {"valid": True, "failed": 0},
                "semantic": {"valid": False, "error_count": 2},
            },
        )
        assert should_repair(state) == "repair"  # type: ignore[arg-type]

    def test_force_export_after_max_attempts(self) -> None:
        from agent.graph import should_repair

        state = _minimal_state(
            repair_attempts=3,
            validation_results={
                "valid": False,
                "schema": {"valid": False, "error_count": 5},
                "ids": {"valid": False, "failed": 2},
                "semantic": {"valid": False, "error_count": 3},
            },
        )
        assert should_repair(state) == "export"  # type: ignore[arg-type]

    def test_repair_attempt_2_still_repairs(self) -> None:
        from agent.graph import should_repair

        state = _minimal_state(
            repair_attempts=2,
            validation_results={
                "valid": False,
                "schema": {"valid": False, "error_count": 1},
                "ids": {"valid": True, "failed": 0},
                "semantic": {"valid": True, "error_count": 0},
            },
        )
        assert should_repair(state) == "repair"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 4.3 — Repair node
# ---------------------------------------------------------------------------


class TestRepairModule:
    def test_repair_module_importable(self) -> None:
        from agent import repair  # noqa: F401

    def test_classify_error_known_category(self) -> None:
        from agent.repair import classify_error

        assert classify_error({"message": "no spatial container"}) == "no_spatial_container"
        assert classify_error({"message": "Pset_ property missing"}) == "missing_pset"
        assert classify_error({"message": "FillsVoids not filling"}) == "floating_opening"

    def test_classify_error_unknown(self) -> None:
        from agent.repair import classify_error

        assert classify_error({"message": "completely unrecognized error xyz"}) == "unknown"

    def test_build_repair_prompt_includes_errors(self) -> None:
        from agent.repair import build_repair_prompt

        validation = {
            "schema": {"valid": False, "errors": [{"message": "Pset_ missing"}]},
            "ids": {"valid": True, "specifications": []},
            "semantic": {"valid": True, "issues": []},
        }
        prompt = build_repair_prompt(validation, "scene overview text", repair_attempt=1)
        assert "Repair Attempt 1/3" in prompt
        assert "scene overview text" in prompt
        assert "Pset_" in prompt or "missing_pset" in prompt

    def test_build_repair_prompt_attempt_counter(self) -> None:
        from agent.repair import build_repair_prompt

        for attempt in [1, 2, 3]:
            prompt = build_repair_prompt({}, "overview", repair_attempt=attempt)
            assert f"Repair Attempt {attempt}/3" in prompt

    def test_repair_node_increments_counter(self) -> None:
        from agent.repair import repair_node

        state = _minimal_state(
            repair_attempts=1,
            validation_results={
                "schema": {"valid": False, "errors": [{"message": "test error"}]},
                "ids": {"valid": True, "specifications": []},
                "semantic": {"valid": True, "issues": []},
            },
        )
        result = asyncio.run(repair_node(state))
        assert result["repair_attempts"] == 2

    def test_repair_node_skips_when_no_errors(self) -> None:
        from agent.repair import repair_node

        state = _minimal_state(
            repair_attempts=0,
            validation_results={
                "schema": {"valid": True},
                "ids": {"valid": True},
                "semantic": {"valid": True},
            },
        )
        result = asyncio.run(repair_node(state))
        assert result["repair_attempts"] == 1
        assert len(result["messages"]) == 0

    def test_repair_node_appends_message_on_errors(self) -> None:
        from agent.repair import repair_node

        state = _minimal_state(
            repair_attempts=0,
            validation_results={
                "schema": {"valid": False, "errors": [{"message": "missing property"}]},
                "ids": {"valid": True, "specifications": []},
                "semantic": {"valid": True, "issues": []},
            },
        )
        result = asyncio.run(repair_node(state))
        assert len(result["messages"]) == 1


# ---------------------------------------------------------------------------
# 4.4 — Export node writes report
# ---------------------------------------------------------------------------


class TestExportNode:
    def test_present_and_export_writes_report(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        from agent.graph import present_and_export

        state = _minimal_state(
            building_plan={"plan_id": "test01", "description": "Test plan"},
            validation_results={"valid": True},
            tool_calls_log=[{"tool": "create_wall", "status": "queued"}],
            final_ifc_path="tests/output/golden_simple_room.ifc",
        )
        result = present_and_export(state)  # type: ignore[arg-type]

        reports_dir = tmp_path / "reports"
        assert reports_dir.exists(), "reports/ directory not created"

        report_files = list(reports_dir.glob("run_test01_*.json"))
        assert len(report_files) == 1, f"Expected 1 report file, found {len(report_files)}"

        with open(report_files[0]) as f:
            report = json.load(f)

        assert report["plan_id"] == "test01"
        assert "validation_results" in report
        assert "tool_calls_log" in report
        assert "timestamp" in report
        assert result is not None

    def test_export_report_has_required_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        from agent.graph import present_and_export

        state = _minimal_state(building_plan={"plan_id": "chk99"})
        present_and_export(state)  # type: ignore[arg-type]

        reports = list((tmp_path / "reports").glob("run_chk99_*.json"))
        assert reports
        data = json.loads(reports[0].read_text())
        for key in ("plan_id", "timestamp", "repair_attempts", "validation_results", "tool_calls_log"):
            assert key in data, f"Report missing key: {key}"


# ---------------------------------------------------------------------------
# 4.5 — Node smoke tests (minimal state, no MCP)
# ---------------------------------------------------------------------------


class TestNodeSmoke:
    def test_intake_node(self) -> None:
        from langchain_core.messages import HumanMessage

        from agent.graph import intake_and_constraints

        state = _minimal_state(messages=[HumanMessage(content="Build a simple room")])
        result = intake_and_constraints(state)  # type: ignore[arg-type]
        assert "building_plan" in result
        assert "repair_attempts" in result

    def test_generate_plan_node(self) -> None:
        from langchain_core.messages import HumanMessage

        from agent.graph import generate_plan

        state = _minimal_state(messages=[HumanMessage(content="Build a house")])
        result = generate_plan(state)  # type: ignore[arg-type]
        assert "messages" in result
        assert len(result["messages"]) > 0

    def test_execute_build_steps_empty_plan(self) -> None:
        from agent.graph import execute_build_steps

        state = _minimal_state(building_plan={})
        result = execute_build_steps(state)  # type: ignore[arg-type]
        assert "tool_calls_log" in result

    def test_validate_node_no_ifc_path(self) -> None:
        from agent.graph import validate

        state = _minimal_state(final_ifc_path="")
        result = validate(state)  # type: ignore[arg-type]
        assert "validation_results" in result
        assert result["validation_results"]["valid"] is True


# ---------------------------------------------------------------------------
# 4.6 — Module docstrings for agent/
# ---------------------------------------------------------------------------


class TestAgentDocstrings:
    @pytest.mark.parametrize(
        "py_file",
        [p.name for p in _collect_py_files(AGENT_ROOT) if p.name != ".gitkeep"],
        ids=lambda name: name,
    )
    def test_has_module_docstring(self, py_file: str) -> None:
        path = next(AGENT_ROOT.rglob(py_file))
        assert _has_module_docstring(path), (
            f"{path.relative_to(PROJECT_ROOT)} is missing a module docstring"
        )
