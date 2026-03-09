"""LangGraph orchestration for LLM→IFC generation.

State machine:
  intake_and_constraints → generate_plan → execute_build_steps
      → validate → [repair loop, max 3x] → present_and_export
"""
from __future__ import annotations

import json
import logging
import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool governance — allowed tools per stage
# ---------------------------------------------------------------------------

PLAN_TOOLS = [
    "search_ifc_knowledge",
    "find_ifc_function",
    "get_ifc_scene_overview",
]

BUILD_TOOLS = [
    "create_wall",
    "create_two_point_wall",
    "create_polyline_walls",
    "create_slab",
    "create_door",
    "create_window",
    "create_roof",
    "create_stairs",
    "create_surface_style",
    "apply_style_to_object",
]

VALIDATE_TOOLS = [
    "get_wall_properties",
    "get_slab_properties",
    "get_door_properties",
    "get_window_properties",
    "get_ifc_scene_overview",
    "get_object_info",
]

REPAIR_TOOLS = BUILD_TOOLS + [
    "update_wall",
    "update_slab",
    "update_door",
    "update_window",
    "update_roof",
    "update_stairs",
    "execute_ifc_code_tool",
]

EXPORT_TOOLS = [
    "capture_blender_3dviewport_screenshot",
]


# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """Shared state flowing through every graph node."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    building_plan: Dict[str, Any]
    tool_calls_log: List[Dict[str, Any]]
    validation_results: Dict[str, Any]
    repair_attempts: int
    final_ifc_path: str
    ids_report_path: str
    scene_overview: str


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


def intake_and_constraints(state: AgentState) -> AgentState:
    """Parse user prompt, extract building requirements.

    Reads the last HumanMessage and stores the raw prompt for the planner.
    In a full deployment this node would run an LLM to extract structured
    constraints; here it passes the messages through unchanged.
    """
    logger.info("[intake] Parsing user prompt and constraints")
    messages = list(state.get("messages", []))

    if not messages:
        logger.warning("[intake] No messages in state — nothing to parse")
        return {
            **state,
            "building_plan": {},
            "tool_calls_log": [],
            "validation_results": {},
            "repair_attempts": 0,
            "final_ifc_path": "",
            "ids_report_path": "",
            "scene_overview": "",
        }

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)),
        None,
    )
    prompt_text = last_human.content if last_human else ""
    logger.info(f"[intake] User prompt: {prompt_text[:120]}...")

    return {
        **state,
        "building_plan": state.get("building_plan", {}),
        "tool_calls_log": state.get("tool_calls_log", []),
        "validation_results": state.get("validation_results", {}),
        "repair_attempts": state.get("repair_attempts", 0),
        "final_ifc_path": state.get("final_ifc_path", ""),
        "ids_report_path": state.get("ids_report_path", ""),
        "scene_overview": state.get("scene_overview", ""),
    }


def generate_plan(state: AgentState) -> AgentState:
    """LLM generates a structured BuildingPlan using the component registry.

    Allowed tools at this stage: PLAN_TOOLS (read-only).
    The plan is stored as a dict in state["building_plan"].
    """
    logger.info("[plan] Generating structured building plan")

    system_prompt = SystemMessage(
        content=(
            "You are an IFC building model planner. "
            "Given the user's building description, produce a structured JSON "
            "BuildingPlan following the schema in agent/schemas.py. "
            "Available read-only tools: "
            + ", ".join(PLAN_TOOLS)
        )
    )

    return {
        **state,
        "messages": list(state["messages"]) + [system_prompt],
    }


def execute_build_steps(state: AgentState) -> AgentState:
    """Execute MCP tool calls derived from the building plan.

    Allowed tools: BUILD_TOOLS only.
    Each executed tool call is appended to tool_calls_log.
    """
    logger.info("[build] Executing build steps from plan")

    plan = state.get("building_plan", {})
    if not plan:
        logger.warning("[build] No building plan found — skipping execution")
        return state

    from agent.schemas import BuildingPlan, plan_to_tool_calls  # local import to avoid circular

    try:
        building_plan_obj = BuildingPlan.model_validate(plan)
        tool_calls = plan_to_tool_calls(building_plan_obj)
    except Exception as exc:
        logger.error(f"[build] Failed to convert plan to tool calls: {exc}")
        return {
            **state,
            "tool_calls_log": state.get("tool_calls_log", [])
            + [{"error": str(exc), "stage": "build"}],
        }

    log_entries: List[Dict[str, Any]] = []
    for call in tool_calls:
        log_entries.append(
            {
                "stage": "build",
                "tool": call["tool"],
                "args": call.get("args", {}),
                "metadata": call.get("metadata", {}),
                "status": "queued",
            }
        )
        logger.info(f"[build] Queued: {call['tool']} {list(call.get('args', {}).keys())}")

    return {
        **state,
        "tool_calls_log": state.get("tool_calls_log", []) + log_entries,
    }


def validate(state: AgentState) -> AgentState:
    """Run all three validation layers: schema, IDS, semantic.

    Allowed tools: VALIDATE_TOOLS (read-only).
    Results are stored in state["validation_results"].
    """
    logger.info("[validate] Running validation layers")

    ifc_path = state.get("final_ifc_path", "")
    ids_path = state.get("ids_report_path", "")

    schema_result: Dict[str, Any] = {"valid": True, "errors": [], "error_count": 0}
    ids_result: Dict[str, Any] = {"valid": True, "specifications": [], "failed": 0}
    semantic_result: Dict[str, Any] = {"valid": True, "issues": [], "error_count": 0}

    if ifc_path:
        try:
            from validate.schema_validate import validate_ifc  # type: ignore[import]

            schema_result = validate_ifc(ifc_path)
            logger.info(
                f"[validate] Schema: {'PASS' if schema_result['valid'] else 'FAIL'}"
            )
        except Exception as exc:
            logger.error(f"[validate] Schema validation error: {exc}")
            schema_result = {"valid": False, "errors": [str(exc)], "error_count": 1}

        try:
            from validate.ids_validate import validate_ids  # type: ignore[import]

            if ids_path:
                ids_result = validate_ids(ifc_path, ids_path)
                logger.info(
                    f"[validate] IDS: {'PASS' if ids_result['valid'] else 'FAIL'}"
                )
        except Exception as exc:
            logger.error(f"[validate] IDS validation error: {exc}")
            ids_result = {"valid": False, "specifications": [], "failed": 1, "error": str(exc)}

        try:
            from validate.semantic_checks import run_all_checks

            semantic_result = run_all_checks(ifc_path)
            logger.info(
                f"[validate] Semantic: {'PASS' if semantic_result['valid'] else 'FAIL'} "
                f"({semantic_result['error_count']} errors)"
            )
        except Exception as exc:
            logger.error(f"[validate] Semantic validation error: {exc}")
            semantic_result = {
                "valid": False,
                "issues": [{"message": str(exc)}],
                "error_count": 1,
                "warning_count": 0,
            }
    else:
        logger.warning("[validate] No IFC path set — skipping file-based validation")

    combined: Dict[str, Any] = {
        "valid": (
            schema_result["valid"]
            and ids_result["valid"]
            and semantic_result["valid"]
        ),
        "schema": schema_result,
        "ids": ids_result,
        "semantic": semantic_result,
    }

    return {**state, "validation_results": combined}


def repair(state: AgentState) -> AgentState:
    """Delegate to the repair node implementation in agent/repair.py."""
    import asyncio

    from agent.repair import repair_node

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, repair_node(state))
            return future.result()  # type: ignore[return-value]
    else:
        return loop.run_until_complete(repair_node(state))  # type: ignore[return-value]


def should_repair(
    state: AgentState,
) -> Literal["repair", "export"]:
    """Conditional edge: route to repair or export."""
    v = state.get("validation_results", {})

    if state.get("repair_attempts", 0) >= 3:
        logger.warning("[route] Max repair attempts reached — force-exporting with warnings")
        return "export"

    has_errors = (
        not v.get("schema", {}).get("valid", True)
        or not v.get("ids", {}).get("valid", True)
        or not v.get("semantic", {}).get("valid", True)
    )

    if has_errors:
        total_errors = (
            v.get("schema", {}).get("error_count", 0)
            + v.get("ids", {}).get("failed", 0)
            + v.get("semantic", {}).get("error_count", 0)
        )
        logger.info(f"[route] Routing to repair — {total_errors} errors across all layers")
        return "repair"

    logger.info("[route] All validations passed — routing to export")
    return "export"


def present_and_export(state: AgentState) -> AgentState:
    """Export final IFC and generate summary report to reports/.

    Writes a JSON execution trace to reports/run_<plan_id>.json.
    """
    import json
    import os
    from datetime import datetime, timezone

    logger.info("[export] Generating summary report")

    plan = state.get("building_plan", {})
    plan_id = plan.get("plan_id", "unknown")
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    validation = state.get("validation_results", {})
    tool_log = state.get("tool_calls_log", [])

    report = {
        "plan_id": plan_id,
        "timestamp": timestamp,
        "final_ifc_path": state.get("final_ifc_path", ""),
        "ids_report_path": state.get("ids_report_path", ""),
        "repair_attempts": state.get("repair_attempts", 0),
        "validation_results": validation,
        "tool_calls_count": len(tool_log),
        "tool_calls_log": tool_log,
        "overall_valid": validation.get("valid", False),
    }

    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/run_{plan_id}_{timestamp[:10]}.json"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"[export] Report written to {report_path}")
    except OSError as exc:
        logger.error(f"[export] Failed to write report: {exc}")

    return {**state, "messages": list(state["messages"])}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)

workflow.add_node("intake", intake_and_constraints)
workflow.add_node("plan", generate_plan)
workflow.add_node("build", execute_build_steps)
workflow.add_node("validate", validate)
workflow.add_node("repair", repair)
workflow.add_node("export", present_and_export)

workflow.set_entry_point("intake")
workflow.add_edge("intake", "plan")
workflow.add_edge("plan", "build")
workflow.add_edge("build", "validate")
workflow.add_conditional_edges(
    "validate",
    should_repair,
    {"repair": "repair", "export": "export"},
)
workflow.add_edge("repair", "build")
workflow.add_edge("export", END)

app = workflow.compile()


# ---------------------------------------------------------------------------
# MCP client factory (optional, for live runs)
# ---------------------------------------------------------------------------


async def create_agent(mcp_server_command: Optional[str] = None) -> Any:
    """Create a LangGraph agent connected to the MCP server.

    Args:
        mcp_server_command: Path to the Python interpreter running the MCP server.
            If None, tools must be injected manually.

    Returns:
        The compiled LangGraph app.
    """
    if mcp_server_command is None:
        logger.info("No MCP server command provided — returning graph without live tools")
        return app

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient  # type: ignore[import]

        async with MultiServerMCPClient(
            {
                "ifc-bonsai": {
                    "command": mcp_server_command,
                    "args": ["-m", "blender_mcp.server"],
                    "transport": "stdio",
                }
            }
        ) as client:
            tools = client.get_tools()
            logger.info(f"[mcp] Connected — {len(tools)} tools available")
            return app
    except ImportError:
        logger.warning(
            "langchain-mcp-adapters not installed. "
            "Run: uv add langchain-mcp-adapters"
        )
        return app
