"""Repair node for the LangGraph pipeline.

Takes validation results and the current scene state, then generates
targeted fix operations via the LLM. The LLM receives structured error
data and must output a list of remediation tool calls.

Key design:
- The repair prompt includes the FULL validation error JSON
- The LLM sees the current scene state via get_ifc_scene_overview
- Repair operations are scoped: the LLM can only use update_* and
  limited create_* tools — never delete + recreate (causes GUID churn)
- Max 3 repair iterations before force-export with warnings
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

ERROR_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "missing_pset": {
        "pattern_keywords": ["Pset_", "property", "IsExternal"],
        "repair_strategy": "add_property_set",
        "description": "A required property set or property is missing from an element.",
    },
    "no_spatial_container": {
        "pattern_keywords": [
            "spatial",
            "container",
            "IfcRelContainedInSpatialStructure",
            "no spatial",
        ],
        "repair_strategy": "assign_container",
        "description": "An element is not assigned to any storey.",
    },
    "floating_opening": {
        "pattern_keywords": ["not filling", "FillsVoids", "opening", "floating"],
        "repair_strategy": "reposition_opening",
        "description": "A door or window is not properly hosted in a wall.",
    },
    "schema_error": {
        "pattern_keywords": ["schema", "required attribute", "invalid value"],
        "repair_strategy": "fix_attribute",
        "description": "An IFC schema constraint is violated.",
    },
    "geometry_error": {
        "pattern_keywords": ["zero-thickness", "degenerate", "self-intersecting"],
        "repair_strategy": "fix_geometry",
        "description": "A geometry-level problem (zero thickness, bad shape, etc.).",
    },
}


def classify_error(error: Dict[str, Any]) -> str:
    """Classify a validation error into a repair category.

    Returns the category key from ERROR_CATEGORIES, or 'unknown'.
    """
    error_text = json.dumps(error).lower()
    for category, spec in ERROR_CATEGORIES.items():
        if any(kw.lower() in error_text for kw in spec["pattern_keywords"]):
            return category
    return "unknown"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_repair_prompt(
    validation_results: Dict[str, Any],
    scene_overview: str,
    repair_attempt: int,
    max_attempts: int = 3,
) -> str:
    """Build the LLM prompt for the repair node.

    Includes:
    1. Classified errors with repair hints
    2. Current scene state
    3. Available repair tools
    4. Instructions to output structured fix operations
    """
    all_errors: List[Dict[str, Any]] = []

    for err in validation_results.get("schema", {}).get("errors", []):
        classified = classify_error(err)
        all_errors.append(
            {
                "source": "schema",
                "category": classified,
                "strategy": ERROR_CATEGORIES.get(classified, {}).get(
                    "repair_strategy", "manual"
                ),
                "detail": err,
            }
        )

    for spec in validation_results.get("ids", {}).get("specifications", []):
        if not spec.get("status", True):
            classified = classify_error(spec)
            all_errors.append(
                {
                    "source": "ids",
                    "category": classified,
                    "strategy": ERROR_CATEGORIES.get(classified, {}).get(
                        "repair_strategy", "manual"
                    ),
                    "detail": spec,
                }
            )

    for issue in validation_results.get("semantic", {}).get("issues", []):
        classified = classify_error(issue)
        all_errors.append(
            {
                "source": "semantic",
                "category": classified,
                "strategy": ERROR_CATEGORIES.get(classified, {}).get(
                    "repair_strategy", "manual"
                ),
                "detail": issue,
            }
        )

    errors_json = json.dumps(all_errors, indent=2, default=str)

    prompt = f"""You are an IFC repair specialist. The generated building model has validation errors.

## Repair Attempt {repair_attempt}/{max_attempts}

## Current Scene State
{scene_overview}

## Classified Errors ({len(all_errors)} total)
{errors_json}

## Repair Strategies Available

### For "missing_pset" errors:
Use `execute_ifc_code_tool` to add the missing property set:
```python
import ifcopenshell.api
ifc = ifcopenshell.open("/path/to/file.ifc")
element = ifc.by_guid("ELEMENT_GUID_HERE")
pset = ifcopenshell.api.run("pset.add_pset", ifc, product=element, name="Pset_WallCommon")
ifcopenshell.api.run("pset.edit_pset", ifc, pset=pset, properties={{"IsExternal": True}})
ifc.write("/path/to/file.ifc")
```

### For "no_spatial_container" errors:
Use `execute_ifc_code_tool` to assign the element to a storey:
```python
storey = ifc.by_type("IfcBuildingStorey")[0]  # or find correct storey
ifcopenshell.api.run("spatial.assign_container", ifc, relating_structure=storey, products=[element])
```

### For "floating_opening" errors:
Use `update_door` or `update_window` to reposition the opening closer to its host wall.

### For "schema_error" errors:
Fix the specific attribute. Refer to the error message for which attribute is invalid.

## Output Format
Return a JSON array of fix operations:
```json
[
  {{
    "error_index": 0,
    "tool": "execute_ifc_code_tool",
    "args": {{"code": "...python code..."}},
    "explanation": "Adding missing Pset_WallCommon to wall W1"
  }}
]
```

Only fix errors you are confident about. If an error is unclear, skip it and add a note.
Do NOT delete and recreate elements — this causes GUID churn and breaks references.
"""
    return prompt


# ---------------------------------------------------------------------------
# Repair executor
# ---------------------------------------------------------------------------


def execute_repairs(
    fix_operations: List[Dict[str, Any]],
    mcp_client: Any,
) -> List[Dict[str, Any]]:
    """Execute a list of repair operations via MCP tools.

    Returns a list of results, one per operation.
    """
    results: List[Dict[str, Any]] = []
    for i, op in enumerate(fix_operations):
        tool_name = op.get("tool", "unknown")
        args = op.get("args", {})
        explanation = op.get("explanation", "No explanation")

        logger.info(f"Repair [{i + 1}/{len(fix_operations)}]: {explanation}")
        logger.info(f"  Tool: {tool_name}, Args keys: {list(args.keys())}")

        try:
            result = mcp_client.call_tool(tool_name, args)
            results.append(
                {
                    "operation_index": i,
                    "tool": tool_name,
                    "status": "success",
                    "result": str(result)[:500],
                    "explanation": explanation,
                }
            )
            logger.info("  Success")
        except Exception as exc:
            results.append(
                {
                    "operation_index": i,
                    "tool": tool_name,
                    "status": "error",
                    "error": str(exc),
                    "explanation": explanation,
                }
            )
            logger.error(f"  Failed: {exc}")

    return results


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


async def repair_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph repair node implementation.

    1. Reads validation_results from state
    2. Gets current scene overview from state (populated by validate node)
    3. Builds repair prompt
    4. Appends prompt as HumanMessage for the LLM
    5. Increments repair_attempts counter
    """
    validation = state.get("validation_results", {})
    attempt = state.get("repair_attempts", 0) + 1

    has_errors = (
        not validation.get("schema", {}).get("valid", True)
        or not validation.get("ids", {}).get("valid", True)
        or not validation.get("semantic", {}).get("valid", True)
    )

    if not has_errors:
        logger.info("[repair] No errors to repair — skipping repair node")
        return {**state, "repair_attempts": attempt}

    logger.info(f"[repair] Repair attempt {attempt}/3")

    scene_overview = state.get("scene_overview", "Scene overview not available")
    prompt = build_repair_prompt(validation, scene_overview, attempt)
    repair_message = HumanMessage(content=prompt)

    tool_log_entry: Dict[str, Any] = {
        "stage": "repair",
        "attempt": attempt,
        "error_counts": {
            "schema": validation.get("schema", {}).get("error_count", 0),
            "ids": validation.get("ids", {}).get("failed", 0),
            "semantic": validation.get("semantic", {}).get("error_count", 0),
        },
    }

    return {
        **state,
        "messages": list(state.get("messages", [])) + [repair_message],
        "repair_attempts": attempt,
        "tool_calls_log": state.get("tool_calls_log", []) + [tool_log_entry],
    }
