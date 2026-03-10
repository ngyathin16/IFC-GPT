---
description: Run the complete LLM→IFC pipeline from prompt to validated output
---

# Full Pipeline Workflow

## Input
Ask the user for the building description prompt (free-form text).

## Step 1: Verify Prerequisites
- Confirm Blender is running with Bonsai addon loaded.
- Confirm the embedding server is running on port 8080.
- Confirm `uv run python -m blender_mcp.server` responds to `ping`.

## Step 2: Run Agent Pipeline
Run `uv run python -m agent.graph "<user_prompt>"` and monitor stdout for stage transitions:
```
[intake] Extracting constraints...
[plan] Generating BuildingPlan...
[build] Executing 8 MCP tool calls...
[validate] Running 3-layer validation...
[export] Writing output.ifc...
```

## Step 3: Validate Output
Follow the `/validate-ifc` workflow on the generated `output.ifc`.

## Step 4: Full Report
Display the execution summary:

**BuildingPlan Summary**
- Storeys: N
- Elements: N walls, N slabs, N doors, N windows, N roofs

**MCP Tool Calls**
List each call: tool name → result GUID (or error)

**Validation Results**
| Layer | Result | Errors |
|-------|--------|--------|
| Schema | PASS/FAIL | N |
| IDS | X/13 | N |
| Semantic | PASS/FAIL | N |

**Repair Operations** (if any)
- Attempt 1: N fixes applied
- Re-validation: X/13 → Y/13

**Final Artifacts**
- IFC file: `output/<plan_id>.ifc`
- IDS report: `reports/ids_<plan_id>.html`
- Execution trace: `reports/run_<plan_id>.json`
- Total pipeline time: ~N seconds
