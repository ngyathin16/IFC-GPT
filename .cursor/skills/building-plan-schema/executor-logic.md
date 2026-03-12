# Executor Logic — plan_to_tool_calls()

## Purpose
Translates a `BuildingPlan` (LLM output) into an ordered list of MCP tool calls with resolved global coordinates.

## Execution Order (enforced)
1. **Walls** — must exist before openings can reference them
2. **Slabs** — floor/ceiling geometry
3. **Openings** (doors + windows) — after walls, uses `guid_map` for host wall GUID lookup
4. **Roof** — after walls establish height
5. **Stairs** — after both storeys have walls

## Key Function: `plan_to_tool_calls`

```python
def plan_to_tool_calls(plan: BuildingPlan, storey_elevations: dict[str, float]) -> list[ToolCall]:
    """
    Convert a BuildingPlan to an ordered list of MCP tool calls.

    Args:
        plan: Validated BuildingPlan instance
        storey_elevations: {storey_ref: elevation_m} mapping

    Returns:
        Ordered list of ToolCall dicts ready for MCP execution
    """
    tool_calls = []
    wall_registry: dict[str, WallPlacement] = {}  # wall_ref -> placement

    # Pass 1: Walls
    for elem in plan.elements:
        if elem.element_type == "wall":
            storey_z = storey_elevations[elem.storey_ref]
            tool_calls.append({
                "tool": "create_two_point_wall",
                "args": {
                    "name": elem.wall_ref,
                    "start_point": [elem.start_point[0], elem.start_point[1], storey_z],
                    "end_point": [elem.end_point[0], elem.end_point[1], storey_z],
                    "thickness": elem.thickness,
                    "height": _get_storey_height(plan, elem.storey_ref),
                },
                "wall_ref": elem.wall_ref,  # used to build guid_map after execution
            })
            wall_registry[elem.wall_ref] = elem

    # Pass 2: Slabs
    for elem in plan.elements:
        if elem.element_type == "slab":
            storey_z = storey_elevations[elem.storey_ref]
            tool_calls.append({
                "tool": "create_slab",
                "args": {
                    "name": f"Slab_{elem.storey_ref}",
                    "polyline": elem.boundary_points,
                    "depth": 0.2,  # from component registry default
                    "location": [0.0, 0.0, storey_z],
                },
            })

    # Pass 3: Openings (doors + windows)
    for elem in plan.elements:
        if elem.element_type in ("door", "window"):
            host_wall = wall_registry[elem.host_wall_ref]
            storey_z = storey_elevations[elem.storey_ref]
            global_pos = _wall_relative_to_global(
                host_wall.start_point, host_wall.end_point,
                elem.distance_along_wall, elem.sill_height, storey_z
            )
            if elem.element_type == "door":
                tool_calls.append({
                    "tool": "create_door",
                    "args": {
                        "name": f"Door_{elem.host_wall_ref}",
                        "dimensions": {"width": elem.width, "height": elem.height},
                        "operation_type": elem.operation_type,
                        "location": global_pos,
                    },
                })
            else:
                tool_calls.append({
                    "tool": "create_window",
                    "args": {
                        "name": f"Window_{elem.host_wall_ref}",
                        "dimensions": {"width": elem.width, "height": elem.height},
                        "partition_type": elem.partition_type,
                        "location": global_pos,
                    },
                })

    # Pass 4: Roofs
    for elem in plan.elements:
        if elem.element_type == "roof":
            tool_calls.append({
                "tool": "create_roof",
                "args": {
                    "polyline": elem.boundary_points,
                    "roof_type": elem.roof_type,
                    "angle": elem.angle,
                    "thickness": elem.thickness,
                },
            })

    # Pass 5: Stairs
    for elem in plan.elements:
        if elem.element_type == "stairs":
            storey_z = storey_elevations[elem.storey_ref]
            target_z = storey_elevations[elem.target_storey_ref]
            tool_calls.append({
                "tool": "create_stairs",
                "args": {
                    "width": elem.width,
                    "height": target_z - storey_z,
                    "stairs_type": elem.stairs_type,
                    "location": [elem.location[0], elem.location[1], storey_z],
                },
            })

    return tool_calls
```

## Key Helper: `_wall_relative_to_global`

```python
import math

def _wall_relative_to_global(
    start: list[float],
    end: list[float],
    distance_along: float,
    sill_height: float,
    storey_z: float,
) -> list[float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx**2 + dy**2)
    t = distance_along / length
    return [
        round(start[0] + t * dx, 4),
        round(start[1] + t * dy, 4),
        round(storey_z + sill_height, 4),
    ]
```

## guid_map Population (in build_node)

After each `create_two_point_wall` call returns, the build node must map `wall_ref → IFC GUID`:

```python
for tool_call, result in zip(wall_tool_calls, wall_results):
    wall_ref = tool_call.get("wall_ref")
    guid = result.get("wall_guid")
    if wall_ref and guid:
        state["guid_map"][wall_ref] = guid
```
