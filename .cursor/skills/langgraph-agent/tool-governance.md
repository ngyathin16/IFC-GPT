# Tool Governance — Per-Stage MCP Tool Allowlists

## Rationale
Constraining which MCP tools each stage can use:
1. Prevents accidental mutations during planning/validation
2. Reduces LLM hallucination of invalid tool sequences
3. Makes repair operations auditable and predictable

## Stage-by-Stage Allowlists

### INTAKE_TOOLS (read-only, no MCP needed)
The intake stage uses only the LLM — no MCP tools.

### PLAN_TOOLS (read-only inspection)
```python
PLAN_TOOLS = [
    "get_ifc_scene_overview",      # Check current scene state
    "search_ifc_knowledge",        # RAG queries for IFC specs
    "find_ifc_function",           # Look up MCP tool parameters
    "get_ifc_function_details",    # Full tool docs
    "list_ifc_entities",           # Valid IFC class names
]
```

### BUILD_TOOLS (create only)
```python
BUILD_TOOLS = [
    "create_wall",
    "create_two_point_wall",
    "create_polyline_walls",
    "create_slab",
    "create_door",
    "create_window",
    "create_roof",
    "create_stairs",
    "get_ifc_scene_overview",      # Scene refresh after each batch
]
```

### VALIDATE_TOOLS (read-only inspection)
```python
VALIDATE_TOOLS = [
    "get_ifc_scene_overview",
    "get_scene_info",
    "get_object_info",
    "get_wall_properties",
    "get_slab_properties",
    "get_door_properties",
    "get_window_properties",
]
```

### REPAIR_TOOLS (create + update + targeted code execution)
```python
REPAIR_TOOLS = [
    # Updates
    "update_wall", "update_slab", "update_door", "update_window", "update_roof", "update_stairs",
    # Targeted code (for pset additions, spatial containment fixes)
    "execute_ifc_code_tool",       # Sandboxed — allowed in repair
    # Inspection (for context)
    "get_ifc_scene_overview",
    "get_object_info",
    # Style (for completeness checks)
    "apply_style_to_object",
]
# NEVER allow in automated repair:
REPAIR_FORBIDDEN = ["execute_blender_code"]
```

## Enforcement Pattern (in agent/graph.py)

```python
from langgraph.prebuilt import ToolNode

build_tool_node = ToolNode(
    tools=[t for t in all_tools if t.name in BUILD_TOOLS]
)
repair_tool_node = ToolNode(
    tools=[t for t in all_tools if t.name in REPAIR_TOOLS]
)
```

## Tool Call Logging

Every tool call is appended to `state["tool_calls_log"]`:
```python
{
    "stage": "build",
    "tool": "create_two_point_wall",
    "args": {"start_point": [0,0,0], "end_point": [5,0,0], ...},
    "result": {"wall_guid": "2F8kN3zP..."},
    "timestamp_ms": 1234567890
}
```
