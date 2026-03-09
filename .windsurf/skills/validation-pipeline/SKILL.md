---
name: validation-pipeline
description: IFC validation pipeline including schema validation, IDS checks, and semantic geometry analysis. Use when writing or modifying validation code.
---

## Three-Layer Validation
1. **Schema validation** (`validate/schema_validate.py`) — Uses `ifcopenshell.validate`
2. **IDS validation** (`validate/ids_validate.py`) — Uses `ifctester` against `ids/v0.ids`
3. **Semantic checks** (`validate/semantic_checks.py`) — Custom spatial/geometry rules

## Key Libraries
- `ifcopenshell.validate` — Schema-level validation
- `ifctester` (pip install ifctester) — IDS validation with HTML/JSON/BCF reports
- `ifcopenshell.util.element` — Element traversal utilities

## IDS File Format
IDS files are XML-based. See https://github.com/buildingSMART/IDS for schema.
Our v0 IDS (`ids/v0.ids`) checks 13 specifications:
- Spatial structure existence: IfcProject, IfcSite, IfcBuilding, IfcBuildingStorey
- Pset_WallCommon.IsExternal, Pset_SlabCommon.IsExternal, Pset_DoorCommon.IsExternal, Pset_WindowCommon.IsExternal
- Spatial containment (partOf IfcBuildingStorey) for walls, slabs, doors, windows, roofs

## Validation Output Contract
All validators return a dict compatible with:
```json
{
  "valid": true,
  "error_count": 0,
  "warning_count": 0,
  "errors": [],
  "warnings": []
}
```
This contract is consumed by the LangGraph repair node.

## Running Validators
```bash
# Schema
python validate/schema_validate.py output.ifc

# IDS
python validate/ids_validate.py output.ifc ids/v0.ids

# Semantic
python validate/semantic_checks.py output.ifc

# IDS via CLI (HTML report)
python -m ifctester ids/v0.ids output.ifc -r Html -o reports/ids_v0_report.html

# IDS via CLI (JSON report)
python -m ifctester ids/v0.ids output.ifc -r Json -o reports/ids_v0_report.json
```

## Adding New Checks
- **Schema**: No code change needed — ifcopenshell.validate handles all IFC4 schema rules.
- **IDS**: Add `<specification>` blocks to `ids/v0.ids`.
- **Semantic**: Add a new `check_*` function to `validate/semantic_checks.py` and call it in `run_all_checks`.

## Test Fixtures
Golden IFC files used for validation tests live in `tests/output/`:
- `golden_simple_room.ifc` — Single rectangular room, 4 walls, 1 slab, 1 door, 1 window
- `golden_two_storey.ifc` — Two-storey building with full spatial hierarchy

Run Phase 3 tests with: `pytest tests/test_phase3.py -v`
