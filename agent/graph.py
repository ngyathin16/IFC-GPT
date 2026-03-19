"""LangGraph orchestration for LLM→IFC generation.

State machine:
  intake → clarify (loop until confirmed) → plan → build (parallel subagents)
      → validate → [repair loop, max 3x] → export
"""
from __future__ import annotations

import asyncio
import json
import logging
import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
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
# Required clarification fields
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: List[str] = [
    "building_type",
    "num_storeys",
    "footprint_dims",
    "room_program",
    "structural_system",
    "wall_thickness",
    "roof_type",
    "special_elements",
    "output_filename",
    "ids_requirements",
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
    # Clarification phase
    requirements: Dict[str, Any]     # accumulated answers from user
    clarification_done: bool         # True once all 10 fields are confirmed
    clarify_rounds: int              # how many clarify iterations have run
    # Subagent tracking
    subagent_statuses: Dict[str, str]  # e.g. {"A": "done", "B": "pending"}
    # Live Blender MCP connection (None = dry-run mode)
    mcp_client: Optional[Any]


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


def intake_and_constraints(state: AgentState) -> AgentState:
    """Initialise state fields and log the incoming user prompt."""
    logger.info("[intake] Parsing user prompt and constraints")
    messages = list(state.get("messages", []))

    if not messages:
        logger.warning("[intake] No messages in state — nothing to parse")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)),
        None,
    )
    prompt_text = last_human.content if last_human else ""
    logger.info(f"[intake] User prompt: {prompt_text[:120]}...")

    from agent.prompts import SYSTEM_PROMPT  # local import — avoids circular at module load

    system_msg = SystemMessage(content=SYSTEM_PROMPT)

    return {
        **state,
        "messages": [system_msg] + messages,
        "building_plan": state.get("building_plan", {}),
        "tool_calls_log": state.get("tool_calls_log", []),
        "validation_results": state.get("validation_results", {}),
        "repair_attempts": state.get("repair_attempts", 0),
        "final_ifc_path": state.get("final_ifc_path", ""),
        "ids_report_path": state.get("ids_report_path", ""),
        "scene_overview": state.get("scene_overview", ""),
        "requirements": state.get("requirements", {}),
        "clarification_done": state.get("clarification_done", False),
        "clarify_rounds": state.get("clarify_rounds", 0),
        "subagent_statuses": state.get("subagent_statuses", {}),
    }


# Sensible defaults applied when no user answer is available
_REQUIREMENT_DEFAULTS: Dict[str, Any] = {
    "building_type": "residential",
    "num_storeys": 5,
    "footprint_dims": "20x15",
    "room_program": "open-plan office floor per storey",
    "structural_system": "concrete frame",
    "wall_thickness": 0.2,
    "roof_type": "flat",
    "special_elements": "stairs",
    "output_filename": "building",
    "ids_requirements": "none",
}


def clarify(state: AgentState) -> AgentState:
    """Extract requirements from conversation; apply defaults after first round.

    Batch-mode behaviour (no live user):
      - Round 1: attempt to extract whatever the user mentioned in their
        initial prompt, then fill remaining fields with defaults and proceed.
      - Interactive mode: ask follow-up questions on round 1, wait for answers
        on subsequent rounds.

    clarify_rounds tracks how many times this node has run so we never loop
    indefinitely.
    """
    logger.info("[clarify] Checking for missing requirements")

    from agent.llm import get_llm

    messages = list(state.get("messages", []))
    requirements: Dict[str, Any] = dict(state.get("requirements", {}))
    rounds: int = state.get("clarify_rounds", 0) + 1

    extract_system = SystemMessage(
        content=(
            "You are an assistant that extracts structured building requirements "
            "from a conversation.  The required fields are: "
            + ", ".join(REQUIRED_FIELDS)
            + ".  "
            "Given the conversation so far, return a JSON object with the fields "
            "you can confidently extract.  Use null for fields that are unknown or "
            "not yet answered.  Return ONLY valid JSON — no markdown, no commentary."
        )
    )

    llm = get_llm(temperature=0.0)

    try:
        extract_response = llm.invoke([extract_system] + list(messages))
        raw = extract_response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        extracted: Dict[str, Any] = json.loads(raw)
        for field in REQUIRED_FIELDS:
            val = extracted.get(field)
            if val is not None:
                requirements[field] = val
        logger.info(f"[clarify] Extracted fields: {list(requirements.keys())}")
    except Exception as exc:
        logger.warning(f"[clarify] Extraction failed: {exc} — continuing with current requirements")

    missing = [f for f in REQUIRED_FIELDS if not requirements.get(f)]

    if not missing:
        logger.info("[clarify] All requirements gathered — proceeding to plan")
        req_lines = "\n".join(f"  {k}: {v}" for k, v in requirements.items())
        confirm_msg = AIMessage(
            content=(
                f"\u2705 All requirements confirmed:\n{req_lines}\n\n"
                "Generating building plan\u2026"
            )
        )
        return {
            **state,
            "messages": messages + [confirm_msg],
            "requirements": requirements,
            "clarification_done": True,
            "clarify_rounds": rounds,
        }

    logger.info(f"[clarify] Still missing after round {rounds}: {missing}")

    question_system = SystemMessage(
        content=(
            "You are a friendly BIM assistant collecting building requirements. "
            "The following fields are still unknown: "
            + ", ".join(missing)
            + ".  "
            "Ask the user for ONLY these missing items in a concise numbered list. "
            "Do not ask for fields that are already known. "
            "Do not say anything else."
        )
    )

    try:
        question_response = llm.invoke([question_system] + list(messages))
        question_text = question_response.content
    except Exception as exc:
        logger.error(f"[clarify] LLM question generation failed: {exc}")
        question_text = (
            "Please provide the following details:\n"
            + "\n".join(f"{i+1}. {f}" for i, f in enumerate(missing))
        )

    question_msg = AIMessage(content=question_text)
    return {
        **state,
        "messages": messages + [question_msg],
        "requirements": requirements,
        "clarification_done": False,
        "clarify_rounds": rounds,
    }


def generate_plan(state: AgentState) -> AgentState:
    """LLM generates a structured BuildingPlan using the component registry.

    Uses the confirmed requirements dict to produce a JSON BuildingPlan that
    matches agent/schemas.py exactly.  The plan is stored in
    state["building_plan"].
    """
    logger.info("[plan] Generating structured building plan")

    from agent.llm import get_llm
    from agent.prompts import PLAN_PROMPT_TEMPLATE
    from agent.schemas import BuildingPlan

    requirements = state.get("requirements", {})
    requirements_summary = json.dumps(requirements, indent=2)

    plan_prompt = SystemMessage(
        content=PLAN_PROMPT_TEMPLATE.format(
            requirements_summary=requirements_summary
        )
    )

    llm = get_llm(temperature=0.2)
    messages = list(state["messages"]) + [plan_prompt]

    raw = ""
    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        plan_dict = json.loads(raw)
        BuildingPlan.model_validate(plan_dict)
        logger.info(
            f"[plan] Plan generated: {plan_dict.get('description', '')[:80]}"
        )
        return {
            **state,
            "messages": messages + [response],
            "building_plan": plan_dict,
        }
    except json.JSONDecodeError as exc:
        logger.error(f"[plan] JSON parse failed: {exc}\nRaw output:\n{raw[:2000]}")
        return {**state, "messages": messages, "building_plan": state.get("building_plan", {})}
    except Exception as exc:
        logger.error(
            f"[plan] Plan generation failed: {exc}\nRaw output:\n{raw[:2000]}"
        )
        return {**state, "messages": messages, "building_plan": state.get("building_plan", {})}


# ---------------------------------------------------------------------------
# Parallel subagent helpers
# ---------------------------------------------------------------------------


def _dispatch_subagent(
    label: str,
    calls: List[Dict[str, Any]],
    mcp_tools: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Execute a list of tool calls sequentially via MCP tools.

    ``mcp_tools`` is a dict of {tool_name: LangChain BaseTool} loaded from
    ``load_mcp_tools``.  When None the call is logged as 'queued' (dry-run).

    Returns a list of log entries with status 'success' or 'error'.
    """
    results: List[Dict[str, Any]] = []
    for call in calls:
        tool_name = call["tool"]
        args = call.get("args", {})
        logger.info(f"[subagent-{label}] → {tool_name} {list(args.keys())}")
        entry: Dict[str, Any] = {
            "stage": "build",
            "subagent": label,
            "tool": tool_name,
            "args": args,
            "metadata": call.get("metadata", {}),
        }
        if mcp_tools is not None:
            tool = mcp_tools.get(tool_name)
            if tool is None:
                entry["status"] = "error"
                entry["error"] = f"Tool '{tool_name}' not found in MCP server"
                logger.error(f"[subagent-{label}]   ✗ {tool_name}: not found")
            else:
                try:
                    result = tool.invoke(args)
                    entry["status"] = "success"
                    entry["result"] = str(result)[:500]
                    logger.info(f"[subagent-{label}]   ✓ {tool_name}")
                except Exception as exc:
                    entry["status"] = "error"
                    entry["error"] = str(exc)
                    logger.error(f"[subagent-{label}]   ✗ {tool_name}: {exc}")
        else:
            entry["status"] = "queued"  # dry-run mode
        results.append(entry)
    return results


def execute_build_steps(state: AgentState) -> AgentState:
    """Execute MCP tool calls using parallel subagents (A/B/C/D).

    Subagent decomposition:
      A — Walls   (storey-by-storey, bottom to top)
      B — Slabs   (after A confirms each storey's walls)
      C — Openings (doors then windows; after host walls exist)
      D — Vertical + Roof (stairs after both storeys; roof last)

    B, C, D run concurrently once their A-dependency gates are met.
    In dry-run mode (no mcp_client) all calls are logged as 'queued'.
    """
    logger.info("[build] Executing build steps from plan (parallel subagents)")

    plan = state.get("building_plan", {})
    if not plan:
        logger.warning("[build] No building plan found — skipping execution")
        return state

    from agent.schemas import (
        BuildingPlan,
        OpeningPlacement,
        RoofPlacement,
        SlabPlacement,
        StairsPlacement,
        WallPlacement,
        plan_to_tool_calls,
    )

    try:
        building_plan_obj = BuildingPlan.model_validate(plan)
        all_calls = plan_to_tool_calls(building_plan_obj)
    except Exception as exc:
        logger.error(f"[build] Failed to convert plan to tool calls: {exc}")
        return {
            **state,
            "tool_calls_log": state.get("tool_calls_log", [])
            + [{"error": str(exc), "stage": "build"}],
        }

    # Partition calls into the four subagent buckets
    walls_calls: List[Dict[str, Any]] = []
    slab_calls: List[Dict[str, Any]] = []
    opening_calls: List[Dict[str, Any]] = []
    vertical_calls: List[Dict[str, Any]] = []  # stairs + roof

    for call in all_calls:
        tool = call["tool"]
        if tool in ("create_wall", "create_two_point_wall", "create_polyline_walls"):
            walls_calls.append(call)
        elif tool == "create_slab":
            slab_calls.append(call)
        elif tool in ("create_door", "create_window"):
            opening_calls.append(call)
        else:  # stairs, roof, styles
            vertical_calls.append(call)

    # Enforce roof last inside vertical bucket
    roof_calls = [c for c in vertical_calls if c["tool"] == "create_roof"]
    non_roof_vertical = [c for c in vertical_calls if c["tool"] != "create_roof"]
    vertical_calls = non_roof_vertical + roof_calls

    mcp_tools: Optional[Dict[str, Any]] = state.get("mcp_client")  # dict of tools or None

    log_entries: List[Dict[str, Any]] = []

    # Sequential order: A(walls) → B(slabs) → C(openings) → D(stairs+roof)
    # MCP server handles one request at a time over stdio.
    log_entries.extend(_dispatch_subagent("A-walls", walls_calls, mcp_tools))
    log_entries.extend(_dispatch_subagent("B-slabs", slab_calls, mcp_tools))
    log_entries.extend(_dispatch_subagent("C-openings", opening_calls, mcp_tools))
    log_entries.extend(_dispatch_subagent("D-vertical", vertical_calls, mcp_tools))

    subagent_statuses: Dict[str, str] = {
        "A": "done" if walls_calls else "skipped",
        "B": "done" if slab_calls else "skipped",
        "C": "done" if opening_calls else "skipped",
        "D": "done" if vertical_calls else "skipped",
    }
    logger.info(f"[build] Subagent statuses: {subagent_statuses}")

    return {
        **state,
        "tool_calls_log": state.get("tool_calls_log", []) + log_entries,
        "subagent_statuses": subagent_statuses,
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
    """Delegate to the repair node implementation in agent/repair.py.

    Uses the Azure LLM to interpret validation errors and emit fix operations.
    """
    import asyncio

    from agent.repair import repair_node

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
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
    """Export final IFC, capture viewport screenshot, write summary report.

    Writes a JSON execution trace to reports/run_<plan_id>.json.
    Attempts to capture a Blender viewport screenshot via MCP.
    Appends a user-facing summary AIMessage to state.
    """
    import os
    from datetime import datetime, timezone

    logger.info("[export] Generating summary report")

    plan = state.get("building_plan", {})
    plan_id = plan.get("plan_id", "unknown")
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    validation = state.get("validation_results", {})
    tool_log = state.get("tool_calls_log", [])
    ifc_path = state.get("final_ifc_path", f"workspace/{plan_id}.ifc")

    import base64
    import os

    mcp_tools: Optional[Dict[str, Any]] = state.get("mcp_client")

    # Save IFC via execute_blender_code (bpy is allowed there) and reload viewport
    if mcp_tools is not None:
        try:
            os.makedirs("workspace", exist_ok=True)
            ifc_abs = os.path.abspath(f"workspace/{plan_id}.ifc").replace("\\", "/")
            save_code = (
                "import bpy, bonsai.bim.ifc as bifc\n"
                f"path = r'{ifc_abs}'\n"
                "bifc.IfcStore.path = path\n"
                "bpy.context.scene.BIMProperties.ifc_file = path\n"
                "bifc.IfcStore.file.write(path)\n"
                "bpy.ops.bim.load_project(filepath=path)\n"
                "print('saved:', path)\n"
            )
            exec_tool = mcp_tools.get("execute_blender_code")
            if exec_tool:
                exec_tool.invoke({"code": save_code})
                ifc_path = os.path.abspath(f"workspace/{plan_id}.ifc")
                logger.info(f"[export] IFC saved + viewport reloaded: {ifc_path}")
        except Exception as exc:
            logger.warning(f"[export] Could not save IFC: {exc}")

    # Capture viewport screenshot and save to workspace/
    screenshot_path = ""
    if mcp_tools is not None:
        try:
            ss_tool = mcp_tools.get("capture_blender_3dviewport_screenshot")
            if ss_tool:
                result = ss_tool.invoke({})
                os.makedirs("workspace", exist_ok=True)
                out_png = os.path.abspath(f"workspace/{plan_id}_viewport.png")

                # _DirectMCPTool returns an mcp Image object with .data (bytes)
                try:
                    from mcp.server.fastmcp.utilities.types import Image as MCPImage
                    if isinstance(result, MCPImage):
                        img_bytes = result.data
                        with open(out_png, "wb") as f:
                            f.write(img_bytes)
                        screenshot_path = out_png
                        logger.info(f"[export] Viewport screenshot: {screenshot_path}")
                        result = None  # handled
                except ImportError:
                    pass

                # Fallback: dict or JSON string with base64
                if result is not None:
                    if isinstance(result, str):
                        result = json.loads(result)
                    if isinstance(result, dict):
                        img_field = result.get("data", {}).get("image", "") if "data" in result else result.get("image", "")
                        if isinstance(img_field, dict):
                            b64 = img_field.get("data", "")
                        else:
                            b64 = img_field
                        if b64 and isinstance(b64, str):
                            if "," in b64:
                                b64 = b64.split(",", 1)[1]
                            with open(out_png, "wb") as f:
                                f.write(base64.b64decode(b64))
                            screenshot_path = out_png
                            logger.info(f"[export] Viewport screenshot: {screenshot_path}")
        except Exception as exc:
            logger.warning(f"[export] Could not capture screenshot: {exc}")

    element_count = sum(
        1 for e in tool_log if e.get("stage") == "build" and e.get("status") == "success"
    )
    storey_count = len(plan.get("storeys", []))
    valid_flag = validation.get("valid", False)
    repair_rounds = state.get("repair_attempts", 0)

    report = {
        "plan_id": plan_id,
        "timestamp": timestamp,
        "final_ifc_path": ifc_path,
        "ids_report_path": state.get("ids_report_path", ""),
        "repair_attempts": repair_rounds,
        "validation_results": validation,
        "tool_calls_count": len(tool_log),
        "tool_calls_log": tool_log,
        "overall_valid": valid_flag,
        "screenshot_path": screenshot_path,
    }

    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/run_{plan_id}_{timestamp[:10]}.json"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"[export] Report written to {report_path}")
    except OSError as exc:
        logger.error(f"[export] Failed to write report: {exc}")

    # Build a concise user-facing summary message
    val_icon = "\u2705" if valid_flag else "\u26a0\ufe0f"
    screenshot_line = f"\n- **Viewport screenshot**: `{screenshot_path}`" if screenshot_path else ""
    summary = (
        f"## Build Complete\n\n"
        f"- **Plan ID**: `{plan_id}`\n"
        f"- **IFC file**: `{ifc_path}`\n"
        f"- **Storeys**: {storey_count}\n"
        f"- **Elements built**: {element_count}\n"
        f"- **Validation**: {val_icon} {'PASS' if valid_flag else 'FAIL (see report)'}\n"
        f"- **Repair rounds**: {repair_rounds}/3\n"
        f"- **Report**: `{report_path}`"
        f"{screenshot_line}\n\n"
        f"**What would you like to do?**\n"
        f"  a) Accept and export\n"
        f"  b) Tweak a specific element (describe the change)\n"
        f"  c) Start over with different requirements"
    )

    summary_msg = AIMessage(content=summary)
    return {
        **state,
        "messages": list(state["messages"]) + [summary_msg],
        "final_ifc_path": ifc_path,
    }


# ---------------------------------------------------------------------------
# Conditional edge: clarification loop
# ---------------------------------------------------------------------------


def await_clarification(state: AgentState) -> AgentState:
    """No-op pass-through node used as the loop-back target.

    LangGraph does not allow a conditional edge to route a node back to
    itself.  This node exists purely to provide a distinct graph node that
    the conditional edge on 'clarify' can target, allowing the loop:

        clarify → (done?) → plan
                  (not done?) → await_clarification → clarify
    """
    return state


def should_clarify(
    state: AgentState,
) -> Literal["await_clarification", "plan"]:
    """Route: if all requirements are confirmed go to plan, else loop."""
    if state.get("clarification_done", False):
        return "plan"
    return "await_clarification"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)

workflow.add_node("intake", intake_and_constraints)
workflow.add_node("clarify", clarify)
workflow.add_node("await_clarification", await_clarification)
workflow.add_node("plan", generate_plan)
workflow.add_node("build", execute_build_steps)
workflow.add_node("validate", validate)
workflow.add_node("repair", repair)
workflow.add_node("export", present_and_export)

workflow.set_entry_point("intake")
workflow.add_edge("intake", "clarify")
workflow.add_conditional_edges(
    "clarify",
    should_clarify,
    {"await_clarification": "await_clarification", "plan": "plan"},
)
workflow.add_edge("await_clarification", "clarify")
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
            If None, the graph runs in dry-run mode (tool calls logged but not
            executed against Blender).

    Returns:
        The compiled LangGraph app.
    """
    if mcp_server_command is None:
        logger.info("No MCP server command provided — dry-run mode (no live tools)")
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


class _DirectMCPTool:
    """Thin wrapper that makes an MCP tool function look like a LangChain tool.

    The MCP tool functions in ``blender_mcp.mcp_functions.api_tools`` are
    plain Python callables decorated with ``@mcp.tool()``.  We call them
    directly (same process, same Blender socket) so there is no subprocess or
    MCP protocol overhead.

    The ``ctx`` argument required by some tools is passed as ``None``; the
    tool implementations only use it for logging and it is safe to omit.
    """

    def __init__(self, name: str, fn: Any) -> None:
        self.name = name
        self._fn = fn

    def invoke(self, args: Dict[str, Any]) -> Any:
        import inspect
        sig = inspect.signature(self._fn)
        params = list(sig.parameters.keys())
        # Drop leading 'ctx' parameter if present
        if params and params[0] == "ctx":
            return self._fn(None, **args)
        return self._fn(**args)


def _load_mcp_tools_sync() -> Dict[str, Any]:
    """Load all registered MCP tools and return a {name: _DirectMCPTool} dict.

    Imports the mcp_functions package (registers all @mcp.tool() decorators),
    then asks FastMCP for the list of tool names and wraps each with
    _DirectMCPTool so callers can use .invoke(args).
    """
    # Trigger all @mcp.tool() registrations
    import src.blender_mcp.mcp_functions  # noqa: F401

    from src.blender_mcp.mcp_instance import mcp  # type: ignore[import]

    tool_list = asyncio.run(mcp.list_tools())

    tools: Dict[str, Any] = {}
    for tool_def in tool_list:
        name = tool_def.name

        # Retrieve the underlying Python callable from the tool manager
        raw = mcp._tool_manager._tools.get(name)  # type: ignore[attr-defined]
        if raw is None:
            continue
        fn = raw.fn if hasattr(raw, "fn") else raw
        tools[name] = _DirectMCPTool(name, fn)

    logger.info(f"[mcp] Loaded {len(tools)} direct MCP tools")
    return tools


def run_pipeline(
    user_message: str,
    mcp_client: Any = None,
    interactive: bool = True,
) -> Dict[str, Any]:
    """Run the full IFC generation pipeline.

    In interactive mode (default) the function prints the LLM's clarification
    questions and reads answers from stdin before proceeding to build.
    Set ``interactive=False`` to apply built-in defaults for all missing
    fields without prompting (useful for tests / CI).

    Args:
        user_message: The natural-language building request from the user.
        mcp_client:   Optional live MCP client.  Pass None for dry-run mode.
        interactive:  Whether to prompt the user for missing requirements.

    Returns:
        The final AgentState dict after the graph reaches END.
    """
    from dotenv import load_dotenv
    load_dotenv()

    # -----------------------------------------------------------------------
    # Phase 1 — Clarification loop
    # -----------------------------------------------------------------------
    state: Dict[str, Any] = {
        "messages": [HumanMessage(content=user_message)],
        "building_plan": {},
        "tool_calls_log": [],
        "validation_results": {},
        "repair_attempts": 0,
        "final_ifc_path": "",
        "ids_report_path": "ids/v0.ids",
        "scene_overview": "",
        "requirements": {},
        "clarification_done": False,
        "clarify_rounds": 0,
        "subagent_statuses": {},
        "mcp_client": mcp_client,
    }

    logger.info(f"[pipeline] Starting: {user_message[:80]}...")

    # Connect via MCP stdio transport (same server Windsurf uses)
    if state["mcp_client"] is None:
        try:
            state["mcp_client"] = _load_mcp_tools_sync()
            logger.info(f"[pipeline] Loaded {len(state['mcp_client'])} MCP tools")
        except Exception as exc:
            logger.warning(f"[pipeline] Could not load MCP tools ({exc}) — dry-run mode")

    # Run intake once to inject the system prompt
    state = intake_and_constraints(state)  # type: ignore[arg-type]

    if not interactive:
        # Apply all defaults immediately without asking
        reqs: Dict[str, Any] = dict(state.get("requirements", {}))
        for field in REQUIRED_FIELDS:
            if not reqs.get(field):
                reqs[field] = _REQUIREMENT_DEFAULTS[field]
        state["requirements"] = reqs
        state["clarification_done"] = True
        logger.info("[pipeline] Non-interactive mode — defaults applied")
    else:
        # Interactive: clarify → print question → read input → repeat
        while not state.get("clarification_done", False):
            state = clarify(state)  # type: ignore[arg-type]

            if state.get("clarification_done", False):
                # Print the confirmation message
                msgs = list(state.get("messages", []))
                for m in reversed(msgs):
                    if isinstance(m, AIMessage):
                        print(f"\n{m.content}\n")
                        break
                break

            # Find the latest AIMessage (the question) and print it
            msgs = list(state.get("messages", []))
            question_text = ""
            for m in reversed(msgs):
                if isinstance(m, AIMessage):
                    question_text = m.content
                    break

            if question_text:
                print(f"\n{question_text}\n")

            # Read user answer from stdin
            try:
                answer = input("Your answer: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Interrupted — applying defaults for remaining fields]")
                reqs = dict(state.get("requirements", {}))
                for field in REQUIRED_FIELDS:
                    if not reqs.get(field):
                        reqs[field] = _REQUIREMENT_DEFAULTS[field]
                state["requirements"] = reqs
                state["clarification_done"] = True
                break

            if not answer:
                # Blank answer — apply defaults for all remaining fields
                print("[Applying defaults for unanswered fields]")
                reqs = dict(state.get("requirements", {}))
                for field in REQUIRED_FIELDS:
                    if not reqs.get(field):
                        reqs[field] = _REQUIREMENT_DEFAULTS[field]
                state["requirements"] = reqs
                state["clarification_done"] = True
                break

            # Append the user's answer as a HumanMessage and loop
            state["messages"] = list(state["messages"]) + [
                HumanMessage(content=answer)
            ]

    # -----------------------------------------------------------------------
    # Phase 2 — Plan → Build → Validate → Export
    # -----------------------------------------------------------------------
    logger.info("[pipeline] Clarification complete — starting build graph")

    # Build a sub-graph that starts at 'plan' and ends at END
    build_workflow = StateGraph(AgentState)
    build_workflow.add_node("plan", generate_plan)
    build_workflow.add_node("build", execute_build_steps)
    build_workflow.add_node("validate", validate)
    build_workflow.add_node("repair", repair)
    build_workflow.add_node("export", present_and_export)
    build_workflow.set_entry_point("plan")
    build_workflow.add_edge("plan", "build")
    build_workflow.add_edge("build", "validate")
    build_workflow.add_conditional_edges(
        "validate",
        should_repair,
        {"repair": "repair", "export": "export"},
    )
    build_workflow.add_edge("repair", "build")
    build_workflow.add_edge("export", END)
    build_app = build_workflow.compile()

    final_state = build_app.invoke(state)
    logger.info("[pipeline] Graph complete")
    return final_state
