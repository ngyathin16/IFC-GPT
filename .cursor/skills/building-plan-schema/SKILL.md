---
name: building-plan-schema
description: >
  The BuildingPlan Pydantic schema — the JSON contract between the LLM planner
  node and the executor node. Use when working on agent/schemas.py, the executor,
  or the LLM plan generation prompt.
---

## Schema Architecture
BuildingPlan is a Pydantic BaseModel with:
- `site` (SiteInfo), `building` (BuildingInfo), `storeys` (List[StoreyDefinition])
- `elements` (List[ElementPlacement]) — discriminated union on `element_type`
- `wall_junctions` (List[WallJunction]) — optional topology declarations
- `rooms` (List[RoomDefinition]) — optional semantic labels

## Element Types (discriminated union on `element_type`)
- `WallPlacement`: wall_ref, component_id, start_point [x,y], end_point [x,y], storey_ref
- `OpeningPlacement`: element_type=door|window, host_wall_ref, distance_along_wall, sill_height, width, height
- `SlabPlacement`: boundary_points [[x,y], ...], storey_ref
- `RoofPlacement`: boundary_points [[x,y,z], ...], roof_type, angle, thickness
- `StairsPlacement`: location [x,y], storey_ref, target_storey_ref, stairs_type

## Key Design Decisions
1. LLM reasons in 2D only — Z derived from storey elevation
2. wall_ref = plan-local ID (IFC GUIDs don't exist until creation)
3. distance_along_wall for openings (not global coordinates)
4. Execution order: walls → slabs → openings → roof/stairs
5. **Door host_wall_ref must be an interior corridor wall on all upper floors** — never a perimeter wall above GF unless a balcony is present
6. **Stair core enclosure walls must be added on every storey**, not just ground floor
7. **`IfcStairFlight` geometry must use ShapeBuilder stepped profile** — flat mesh boxes do not render in IFC viewers

## Executor Translation (`agent/schemas.py`)
- `plan_to_tool_calls(plan: BuildingPlan) -> List[ToolCall]`
- `_wall_relative_to_global(wall_start, wall_end, distance_along, sill_height, storey_elevation) -> [x, y, z]`
- Returns ordered list of MCP tool calls with resolved global coordinates

## Coordinate Transform (wall-relative → global)
```python
dx = end[0] - start[0]
dy = end[1] - start[1]
wall_length = sqrt(dx**2 + dy**2)
t = distance_along_wall / wall_length
global_x = start[0] + t * dx
global_y = start[1] + t * dy
global_z = storey_elevation + sill_height
```

## component_id Values
Must match entries in `components/registry.yaml`. Common values:
- `exterior_wall`, `interior_wall`, `ground_slab`, `upper_slab`
- `standard_door`, `double_door`, `standard_window`
- `flat_roof`, `gable_roof`
- `straight_stair` — generates `IfcStairFlight` with ShapeBuilder stepped solid

## Multi-Storey Corridor Layout

For residential or office buildings ≥ 2 storeys, the plan for each upper floor must include:

```
Required elements per upper floor:
  - 4× exterior perimeter walls (IsExternal=True)
  - 2× stair core closing walls per core (IsExternal=False)
  - 1–2× central corridor walls (IsExternal=False) defining the circulation spine
  - N× apartment/office partitions (IsExternal=False)
  - Doors on corridor walls only (host_wall_ref → corridor wall, NOT perimeter wall)
  - Windows on exterior walls only (no windows on interior partitions)
```

Typical corridor wall placement for 20 m × 15 m residential floor:
- Corridor south face: `y = 6.5`, runs `x: 3.0 → 17.0` (between stair cores)
- Corridor north face: `y = 8.0`, runs `x: 3.0 → 17.0`
- Apartment A+B doors: on corridor south wall (`angle_deg=180°`, opening toward apartments)
- Apartment C+D doors: on corridor north wall (`angle_deg=0°`, opening toward apartments)

## IDS Validation Note — `partOf` Relation

The installed `ifctester` XSD accepts only one combined enum value for the fill relation:
- **Correct**: `relation="IFCRELVOIDSELEMENT IFCRELFILLSELEMENT"` (space-separated, both together)
- **Wrong**: `relation="IFCRELFILLSELEMENT"` (standalone — causes `IdsXmlValidationError`)

When this relation is used in a `partOf` requirement for `IfcDoor` / `IfcWindow`, ifctester traverses:
`door/window → IfcRelFillsElement → IfcOpeningElement → IfcRelVoidsElement → IfcWall`

Therefore the `entity/name` in the `partOf` element must be `IFCWALL`, **not** `IFCOPENINGELEMENT`.

## Key Files
- `agent/schemas.py` — Pydantic models + plan_to_tool_calls()
- `components/registry.yaml` — component_id catalog
- `.cursor/skills/building-plan-schema/schema-examples.json` — example BuildingPlan JSONs
- For executor implementation details, see [executor-logic.md](executor-logic.md)
