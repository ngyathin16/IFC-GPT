# AgentState TypedDict Documentation

## Full State Schema

```python
from typing import TypedDict, Annotated, Optional
import operator

class AgentState(TypedDict):
    # Input
    user_prompt: str                          # Raw user input

    # Intake stage output
    constraints: Optional[dict]               # Extracted constraints JSON

    # Plan stage output
    building_plan: Optional[dict]             # BuildingPlan JSON (validated against agent/schemas.py)

    # Build stage output
    tool_calls_log: Annotated[list, operator.add]  # Accumulates across retries
    guid_map: dict                            # wall_ref -> IFC GUID (populated during build)

    # Validation stage output
    validation_results: Optional[dict]        # {schema: {...}, ids: {...}, semantic: {...}}

    # Repair stage
    repair_attempts: int                      # 0..3 (max 3 before force-export)
    repair_ops_log: Annotated[list, operator.add]  # Each repair operation attempted

    # Export stage output
    final_ifc_path: Optional[str]
    ids_report_path: Optional[str]
    execution_report_path: Optional[str]

    # LLM message history (accumulated for multi-turn repair)
    messages: Annotated[list, operator.add]

    # Scene state (refreshed after each build/repair)
    scene_overview: Optional[dict]            # from get_ifc_scene_overview()
```

## State Flow Per Stage

| Stage | Reads | Writes |
|-------|-------|--------|
| `intake_node` | `user_prompt` | `constraints`, `messages` |
| `plan_node` | `constraints`, `messages` | `building_plan`, `messages` |
| `build_node` | `building_plan`, `guid_map` | `tool_calls_log`, `guid_map`, `scene_overview` |
| `validate_node` | `final_ifc_path` | `validation_results` |
| `repair_node` | `validation_results`, `scene_overview`, `repair_attempts` | `messages`, `repair_attempts`, `repair_ops_log` |
| `export_node` | all state | `final_ifc_path`, `ids_report_path`, `execution_report_path` |

## Conditional Edge Logic

```python
def should_repair(state: AgentState) -> str:
    results = state.get("validation_results", {})
    all_valid = all(r.get("valid", False) for r in results.values())
    if all_valid:
        return "export"
    if state.get("repair_attempts", 0) >= 3:
        return "export"  # Force export with warnings
    return "repair"
```

## guid_map Structure

Maps plan-local wall_ref strings to IFC GUIDs for use in opening placement:

```json
{
    "W1": "2F8kN3zP...",
    "W2": "3G9mO4aQ...",
    "W3": "4H0nP5bR...",
    "W4": "5I1oQ6cS..."
}
```

The executor populates this during the wall creation loop, then uses it when creating doors/windows that reference `host_wall_ref`.
