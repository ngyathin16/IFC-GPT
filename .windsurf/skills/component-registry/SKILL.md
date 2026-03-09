---
name: component-registry
description: Building component template registry and deterministic geometry primitives for IFC generation. Use when creating, modifying, or validating building components.
---

## Architecture Decision
We use a YAML registry (`components/registry.yaml`) to define all building primitives.
The LLM must ONLY use registered components — no freehand IfcOpenShell code in v0.

## MCP Tools Available for Building Elements

### Walls
- `create_wall` — Parametric wall with dimensions dict
- `create_two_point_wall` — Wall between two 3D points (most common)
- `create_polyline_walls` — Connected walls along polyline (rooms)

### Slabs
- `create_slab` — Parametric slab with 2D polyline boundary

### Doors & Windows
- `create_door` — With operation_type (SINGLE_SWING_LEFT, etc.)
- `create_window` — With partition_type (SINGLE_PANEL, etc.)
- Both support `location`, `rotation`, `dimensions` dicts

### Roofs
- `create_roof` — From polyline outline with roof_type and angle

### Stairs
- `create_stairs` — Parametric with stairs_type (STRAIGHT, SPIRAL, L_SHAPED, U_SHAPED)

## Coordinate System
- IFC uses meters. All coordinates in meters.
- Z-axis is UP.
- Wall start/end points define the wall center axis.
- Doors/windows positioned relative to global origin, not wall-local.

## Constraints
- Wall thickness: 0.08m–0.5m
- Wall height: 2.4m–6.0m
- Door width: 0.7m–1.2m (single), 1.4m–2.4m (double)
- Window sill height: typically 0.9m–1.2m above floor

## Key Files
- `components/registry.yaml` — Machine-readable catalog of all registered primitives
- `components/primitives.py` — Python functions that compose MCP tool calls
- `agent/schemas.py` — Pydantic BuildingPlan schema (LLM↔Executor contract)

## Primitives Available (`components/primitives.py`)
- `rectangular_room(origin, width, depth, height, wall_thickness, has_slab)` — 4 walls + slab
- `corridor(origin, length, width, height, wall_thickness, axis, has_slab)` — 2 parallel walls + slab
- `stair_core(origin, storey_height, stair_width, landing_depth, wall_thickness, stairs_type)` — stairs + enclosing walls
- `facade_grid(wall_start, wall_end, storey_elevation, num_windows, ...)` — evenly-spaced windows

## BuildingPlan Schema (`agent/schemas.py`)
The LLM outputs a `BuildingPlan` JSON; the executor calls `plan_to_tool_calls(plan)`.

### Element types (discriminated by `element_type` field)
- `"wall"` → `WallPlacement` — uses `wall_ref`, `component_id`, 2D `start_point`/`end_point`
- `"door"` / `"window"` → `OpeningPlacement` — references `host_wall_ref` + `distance_along_wall`
- `"slab"` → `SlabPlacement` — `boundary_points` as 2D polygon
- `"roof"` → `RoofPlacement` — `boundary_points` as 3D polygon
- `"stairs"` → `StairsPlacement` — `storey_ref` + `target_storey_ref`

### Execution order enforced by executor
1. Walls
2. Slabs
3. Openings (doors/windows — after walls exist)
4. Roof and stairs
