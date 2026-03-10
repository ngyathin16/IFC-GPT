---
name: repair-strategy
description: >
  Error classification and automated repair strategies for the LangGraph repair node.
  Use when working on agent/repair.py or debugging validation failures.
---

## Error Categories (10 types)
| Category | Validator | Repair Strategy | Repairable? |
|----------|-----------|-----------------|-------------|
| `missing_pset` | IDS | Add Pset via execute_ifc_code_tool | ✅ Always |
| `no_spatial_container` | IDS/Semantic | spatial.assign_container | ✅ Always |
| `floating_opening` | Semantic | Reposition to nearest wall | ✅ Usually |
| `schema_error` | Schema | Fix attribute per error message | ⚠️ Sometimes |
| `missing_entity` | IDS | Create missing element | ✅ Usually |
| `zero_thickness` | Semantic | Update to minimum thickness | ✅ Always |
| `overlapping_walls` | Semantic | Adjust endpoints | ⚠️ Complex |
| `invalid_hierarchy` | Schema | Rebuild spatial tree | ❌ Regenerate |
| `missing_representation` | Schema | Add geometry representation | ⚠️ Sometimes |
| `invalid_placement` | Schema | Recalculate placement matrix | ⚠️ Sometimes |

## Repair Node Contract (`agent/repair.py`)
- Input: `AgentState` with `validation_results` populated
- Output: `AgentState` with new `messages` entry (repair plan) + incremented `repair_attempts`
- Max 3 attempts: if `repair_attempts >= 3`, route to export with warnings

## Key Functions
- `classify_error(error: dict) -> str` — maps raw validation error to category string
- `build_repair_prompt(state: AgentState) -> str` — structured prompt with categorized errors + scene state
- `execute_repairs(fix_ops: List[dict], tools) -> List[dict]` — executes fix operations
- `repair_node(state: AgentState) -> AgentState` — LangGraph node entry point

## Repair Prompt Structure
1. Categorized error list (not raw JSON) — reduces LLM confusion ~40%
2. Current scene overview from `get_ifc_scene_overview`
3. Category-specific code templates as few-shot examples
4. Output format: JSON array of `{error_index, tool, args, explanation}`

## Fix Operation Pattern (missing_pset example)
```python
{
    "error_index": 0,
    "tool": "execute_ifc_code_tool",
    "args": {
        "code": (
            "import ifcopenshell, ifcopenshell.api\n"
            "from blender_addon.api.ifc_utils import get_ifc_file, save_and_load_ifc\n"
            "ifc = get_ifc_file()\n"
            "element = ifc.by_guid('<GUID>')\n"
            "pset = ifcopenshell.api.run('pset.add_pset', ifc, product=element, name='Pset_DoorCommon')\n"
            "ifcopenshell.api.run('pset.edit_pset', ifc, pset=pset, properties={'IsExternal': True})\n"
            "save_and_load_ifc()"
        )
    },
    "explanation": "Adding missing Pset_DoorCommon.IsExternal to Front Door"
}
```

## Repair Loop Rules
- Max 3 attempts per generation
- Only fix errors you are confident about (high-confidence categories first)
- NEVER delete + recreate elements (breaks GUIDs, cascades failures)
- After each repair: re-validate all 3 layers before next attempt
- If repair_attempts >= 3: force export with `warnings` in report

## Key File
- `agent/repair.py` — repair_node, build_repair_prompt, classify_error, execute_repairs
- `.windsurf/skills/repair-strategy/error-taxonomy.md` — Full error classification table with examples
