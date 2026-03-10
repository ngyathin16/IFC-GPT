---
description: Run full validation pipeline on a generated IFC file
---

# IFC Validation Workflow

## Input
Ask the user for the path to the IFC file to validate. Default: `output.ifc`.

## Step 1: Schema Validation
Run `uv run python validate/schema_validate.py <ifc_path>` and parse the JSON output.

## Step 2: IDS Validation (JSON)
Run `uv run python -m ifctester ids/v0.ids <ifc_path> -r Json -o reports/ids_latest.json` and parse the result.

## Step 3: IDS Validation (HTML Report)
Run `uv run python -m ifctester ids/v0.ids <ifc_path> -r Html -o reports/ids_latest.html` to produce the human-readable report.

## Step 4: Semantic Checks
Run `uv run python validate/semantic_checks.py <ifc_path>` and parse the JSON output.

## Step 5: Combined Report
Display a summary table:

| Layer | Result | Errors | Warnings |
|-------|--------|--------|----------|
| Schema | PASS/FAIL | N | N |
| IDS (13 specs) | X/13 PASS | N | N |
| Semantic | PASS/FAIL | N | N |

- List each specific failure with: layer / element GUID / description / recommended fix.
- Confirm report files generated in `reports/`.
