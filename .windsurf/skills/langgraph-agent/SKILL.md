---
name: langgraph-agent
description: LangGraph orchestration for the LLM→IFC generation pipeline. Use when building or modifying the agent workflow, state graph, or tool governance.
---

## Graph Architecture
intake → plan → build → validate → [repair loop max 3x] → export

## State Schema
AgentState is a TypedDict with: messages, building_plan, tool_calls_log,
validation_results, repair_attempts, final_ifc_path, ids_report_path, scene_overview.

## Tool Governance
- Plan stage: ONLY read-only tools — search_ifc_knowledge, find_ifc_function, get_ifc_scene_overview
- Build stage: ONLY high-level create_* tools from BUILD_TOOLS list in agent/graph.py
- Validate stage: ONLY read-only inspection tools from VALIDATE_TOOLS
- Repair stage: create_* + update_* + execute_ifc_code_tool (last resort)
- NEVER allow execute_blender_code in automated runs (security risk)

## MCP Connection Pattern
Use langchain-mcp-adapters.MultiServerMCPClient with stdio transport.
The MCP server must be running (Blender + addon must be open).

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

async with MultiServerMCPClient({
    "ifc-bonsai": {
        "command": "/path/to/.venv/bin/python",
        "args": ["-m", "blender_mcp.server"],
        "transport": "stdio",
    }
}) as client:
    tools = client.get_tools()
```

## Dependencies
- langgraph >= 0.2.0
- langchain-mcp-adapters
- langchain-openai or langchain-anthropic (for LLM)

## Repair Loop Design
1. Validation returns structured errors in validation_results dict
2. repair_node (agent/repair.py) classifies errors via ERROR_CATEGORIES
3. Repair prompt is built with full error JSON + current scene state
4. LLM message is appended; LLM generates targeted fix operations
5. Build node executes fixes on the next iteration
6. Re-validate. Max 3 attempts (state["repair_attempts"] < 3) before force-export with warnings.

## Error Categories (agent/repair.py)
- missing_pset → add_property_set via execute_ifc_code_tool
- no_spatial_container → assign_container via execute_ifc_code_tool
- floating_opening → reposition via update_door / update_window
- schema_error → fix_attribute
- geometry_error → fix_geometry

## Report Output
Every run writes reports/run_<plan_id>_<date>.json containing:
- execution trace (tool_calls_log)
- full validation_results
- repair_attempts count
- final_ifc_path and ids_report_path

## Key Files
- agent/graph.py — StateGraph definition, node implementations, app = workflow.compile()
- agent/repair.py — repair_node, build_repair_prompt, classify_error, execute_repairs
- agent/schemas.py — BuildingPlan Pydantic schema, plan_to_tool_calls()
