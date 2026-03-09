"""Deterministic geometry primitives that compose MCP tools.

Each primitive is a Python function that takes high-level architectural
parameters and returns a sequence of MCP tool calls with concrete arguments.
"""
from typing import List, Dict, Any, Tuple


def rectangular_room(
    origin: Tuple[float, float, float],
    width: float,
    depth: float,
    height: float = 3.0,
    wall_thickness: float = 0.2,
    has_slab: bool = True,
) -> List[Dict[str, Any]]:
    """Generate MCP tool calls for a rectangular room.

    Returns list of dicts: [{"tool": "create_polyline_walls", "args": {...}}, ...]
    """
    x, y, z = origin
    points = [
        [x, y, z],
        [x + width, y, z],
        [x + width, y + depth, z],
        [x, y + depth, z],
    ]

    calls = [
        {
            "tool": "create_polyline_walls",
            "args": {
                "points": points,
                "name_prefix": "RoomWall",
                "thickness": wall_thickness,
                "height": height,
                "closed": True,
            },
        }
    ]

    if has_slab:
        slab_points = [
            [x, y],
            [x + width, y],
            [x + width, y + depth],
            [x, y + depth],
        ]
        calls.append(
            {
                "tool": "create_slab",
                "args": {
                    "name": "Room Floor",
                    "polyline": slab_points,
                    "depth": 0.2,
                    "location": [0, 0, z],
                },
            }
        )

    return calls


def corridor(
    origin: Tuple[float, float, float],
    length: float,
    width: float = 1.5,
    height: float = 3.0,
    wall_thickness: float = 0.15,
    axis: str = "x",
    has_slab: bool = True,
) -> List[Dict[str, Any]]:
    """Generate MCP tool calls for a straight corridor.

    Two parallel walls along the chosen axis plus an optional slab.

    Args:
        origin: [x, y, z] start corner of the corridor.
        length: Length of the corridor in meters.
        width: Interior clear width of the corridor in meters.
        height: Wall height in meters.
        wall_thickness: Thickness of each side wall in meters.
        axis: "x" for an east-west corridor, "y" for north-south.
        has_slab: Whether to add a floor slab.
    """
    x, y, z = origin

    if axis == "x":
        wall1_start = [x, y, z]
        wall1_end = [x + length, y, z]
        wall2_start = [x, y + width, z]
        wall2_end = [x + length, y + width, z]
        slab_poly = [
            [x, y],
            [x + length, y],
            [x + length, y + width],
            [x, y + width],
        ]
    else:
        wall1_start = [x, y, z]
        wall1_end = [x, y + length, z]
        wall2_start = [x + width, y, z]
        wall2_end = [x + width, y + length, z]
        slab_poly = [
            [x, y],
            [x + width, y],
            [x + width, y + length],
            [x, y + length],
        ]

    calls = [
        {
            "tool": "create_two_point_wall",
            "args": {
                "start_point": wall1_start,
                "end_point": wall1_end,
                "name": "Corridor Wall A",
                "thickness": wall_thickness,
                "height": height,
            },
        },
        {
            "tool": "create_two_point_wall",
            "args": {
                "start_point": wall2_start,
                "end_point": wall2_end,
                "name": "Corridor Wall B",
                "thickness": wall_thickness,
                "height": height,
            },
        },
    ]

    if has_slab:
        calls.append(
            {
                "tool": "create_slab",
                "args": {
                    "name": "Corridor Floor",
                    "polyline": slab_poly,
                    "depth": 0.2,
                    "location": [0, 0, z],
                },
            }
        )

    return calls


def stair_core(
    origin: Tuple[float, float, float],
    storey_height: float,
    stair_width: float = 1.2,
    landing_depth: float = 1.5,
    wall_thickness: float = 0.2,
    stairs_type: str = "STRAIGHT",
) -> List[Dict[str, Any]]:
    """Generate MCP tool calls for a stair core (stairs + enclosing walls).

    The stair core is a rectangular shaft enclosing a straight stair run.
    Walls are placed on all four sides of the shaft.

    Args:
        origin: [x, y, z] bottom-left corner of the stair core.
        storey_height: Total rise (height between floors) in meters.
        stair_width: Clear width of the stairs in meters.
        landing_depth: Depth of the stair run/landing in meters.
        wall_thickness: Enclosing wall thickness in meters.
        stairs_type: IFC stairs type string.
    """
    x, y, z = origin
    shaft_w = stair_width + 2 * wall_thickness
    shaft_d = landing_depth + 2 * wall_thickness

    enclosing_points = [
        [x, y, z],
        [x + shaft_w, y, z],
        [x + shaft_w, y + shaft_d, z],
        [x, y + shaft_d, z],
    ]

    calls = [
        {
            "tool": "create_polyline_walls",
            "args": {
                "points": enclosing_points,
                "name_prefix": "StairWall",
                "thickness": wall_thickness,
                "height": storey_height,
                "closed": True,
            },
        },
        {
            "tool": "create_stairs",
            "args": {
                "width": stair_width,
                "height": storey_height,
                "stairs_type": stairs_type,
                "location": [
                    x + wall_thickness,
                    y + wall_thickness,
                    z,
                ],
            },
        },
    ]

    return calls


def facade_grid(
    wall_start: List[float],
    wall_end: List[float],
    storey_elevation: float,
    num_windows: int,
    window_width: float = 1.2,
    window_height: float = 1.5,
    sill_height: float = 0.9,
    partition_type: str = "SINGLE_PANEL",
) -> List[Dict[str, Any]]:
    """Generate evenly-spaced window placements along a wall face.

    Windows are distributed at regular intervals between wall endpoints.

    Args:
        wall_start: [x, y] start of the host wall (2D).
        wall_end: [x, y] end of the host wall (2D).
        storey_elevation: Z-elevation of the storey floor.
        num_windows: Number of windows to place.
        window_width: Width of each window in meters.
        window_height: Height of each window in meters.
        sill_height: Height from floor to window bottom in meters.
        partition_type: Window partition type string.
    """
    import math

    dx = wall_end[0] - wall_start[0]
    dy = wall_end[1] - wall_start[1]
    wall_length = math.sqrt(dx ** 2 + dy ** 2)

    spacing = wall_length / (num_windows + 1)
    ux, uy = dx / wall_length, dy / wall_length

    calls = []
    for i in range(1, num_windows + 1):
        t = spacing * i
        wx = wall_start[0] + t * ux
        wy = wall_start[1] + t * uy
        wz = storey_elevation + sill_height

        calls.append(
            {
                "tool": "create_window",
                "args": {
                    "name": f"Window_{i}",
                    "dimensions": {
                        "width": window_width,
                        "height": window_height,
                    },
                    "partition_type": partition_type,
                    "location": [round(wx, 4), round(wy, 4), round(wz, 4)],
                },
            }
        )

    return calls
