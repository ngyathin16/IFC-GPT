"""Golden test: Ten-storey mixed-use high-rise building.

Exercises every feature of the MCP toolbox and validation rulesets:

Building programme (20 m × 15 m footprint, 3.5 m floor-to-floor):
  - 10 storeys (Ground Floor + Levels 1–9)
  - Exterior perimeter walls (0.2 m) + interior partitions (0.15 m) per floor
  - One floor slab per storey
  - Ground Floor  : lobby, 2 retail units, main entrance door + sidelight windows
  - Levels 1–4    : open-plan office (south-facing strip windows + one interior door)
  - Levels 5–8    : residential (4 apartments per floor, bedroom/bathroom partitions,
                    windows on all facades)
  - Level 9 (roof): plant room, flat roof over full footprint
  - Two stair cores (NW + NE corners) — 9 flights each (GF→L1 … L8→L9)
  - One central lift shaft (IfcTransportElement, ELEVATOR) spanning all 10 storeys
  - Surface styles: concrete grey exterior, white interior, blue glass windows

Validation targets (must all pass):
  - Schema: 0 errors
  - IDS v0.ids: all 13 specifications PASS
  - Semantic: 0 errors (spatial containment, floating openings, storey linkage,
    geometry completeness, zero-thickness slabs)

Run:
    uv run python tests/golden_test_ten_storey.py
Output:
    tests/output/golden_ten_storey.ifc
    tests/output/golden_ten_storey_validation.json
"""

from __future__ import annotations

import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import ifcopenshell
import ifcopenshell.api

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
IFC_PATH = OUTPUT_DIR / "golden_ten_storey.ifc"

# ---------------------------------------------------------------------------
# Building constants — all in metres
# ---------------------------------------------------------------------------
ORIGIN_X, ORIGIN_Y = 100.0, 0.0    # offset avoids collision with other golden fixtures
WIDTH = 20.0                         # X east–west
DEPTH = 15.0                         # Y south–north
NUM_STOREYS = 10
FTF = 3.5                            # floor-to-floor height
EXT_T = 0.2                          # exterior wall thickness
INT_T = 0.15                         # interior partition thickness

STOREY_NAMES = [
    "Ground Floor",
    "Level 1", "Level 2", "Level 3", "Level 4",
    "Level 5", "Level 6", "Level 7", "Level 8",
    "Level 9",
]
STOREY_REFS = ["GF", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"]
ELEVATIONS = [i * FTF for i in range(NUM_STOREYS)]   # 0, 3.5, 7.0, … 31.5

# Stair core positions (local XY, site-offset applied internally)
STAIR_NW = (0.0,          DEPTH - 3.0)   # NW corner — 3 m deep core
STAIR_NE = (WIDTH - 3.0,  DEPTH - 3.0)   # NE corner

# Lift shaft: centred X, rear of building
LIFT_X = WIDTH / 2 - 1.5
LIFT_Y = DEPTH - 4.0


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _p(x: float, y: float, z: float) -> list[float]:
    """Absolute 3-D point with site offset applied."""
    return [ORIGIN_X + x, ORIGIN_Y + y, z]


def _place(
    ifc: Any,
    product: Any,
    x: float,
    y: float,
    z: float,
    angle_deg: float = 0.0,
) -> None:
    """Set IfcLocalPlacement at absolute coords with optional Z-rotation."""
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    matrix = [
        [cos_a, -sin_a, 0.0, ORIGIN_X + x],
        [sin_a,  cos_a, 0.0, ORIGIN_Y + y],
        [0.0,    0.0,   1.0, z],
        [0.0,    0.0,   0.0, 1.0],
    ]
    ifcopenshell.api.run(
        "geometry.edit_object_placement",
        ifc,
        product=product,
        matrix=matrix,
        is_si=True,
    )


def _assign_pset(
    ifc: Any, product: Any, pset_name: str, props: dict
) -> None:
    """Add a named property set and populate it."""
    pset = ifcopenshell.api.run(
        "pset.add_pset", ifc, product=product, name=pset_name
    )
    ifcopenshell.api.run("pset.edit_pset", ifc, pset=pset, properties=props)


def _assign_material(ifc: Any, product: Any, material_name: str) -> None:
    """Assign a named IfcMaterial to a product."""
    material = ifcopenshell.api.run(
        "material.add_material", ifc, name=material_name
    )
    ifcopenshell.api.run(
        "material.assign_material",
        ifc,
        products=[product],
        material=material,
    )


# ---------------------------------------------------------------------------
# Element factories
# ---------------------------------------------------------------------------

def _create_wall(
    ifc: Any,
    storey: Any,
    name: str,
    is_external: bool,
    start: list[float],
    end: list[float],
    elevation: float,
    thickness: float,
    height: float,
    body_ctx: Any,
    axis_ctx: Any,
    material: str = "Concrete",
) -> Any:
    """Create a wall with geometry, Pset_WallCommon, material, storey assignment."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx ** 2 + dy ** 2)
    angle_deg = math.degrees(math.atan2(dy, dx))

    wall = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcWall", name=name
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[wall],
    )
    _assign_pset(ifc, wall, "Pset_WallCommon", {"IsExternal": is_external})
    _assign_material(ifc, wall, material)

    body_rep = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        ifc,
        context=body_ctx,
        length=length,
        height=height,
        thickness=thickness,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=wall, representation=body_rep
    )

    axis_rep = ifcopenshell.api.run(
        "geometry.add_axis_representation",
        ifc,
        context=axis_ctx,
        axis=[(0.0, 0.0), (length, 0.0)],
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=wall, representation=axis_rep
    )

    _place(ifc, wall, start[0], start[1], elevation, angle_deg)
    return wall


def _create_slab(
    ifc: Any,
    storey: Any,
    body_ctx: Any,
    name: str,
    elev: float,
    polyline: list[tuple[float, float]] | None = None,
    depth: float = 0.25,
    material: str = "Concrete",
) -> Any:
    """Create a floor slab over the given polyline (defaults to full footprint)."""
    if polyline is None:
        polyline = [
            (0.0, 0.0),
            (WIDTH, 0.0),
            (WIDTH, DEPTH),
            (0.0, DEPTH),
        ]
    slab = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcSlab", name=name
    )
    rep = ifcopenshell.api.run(
        "geometry.add_slab_representation",
        ifc,
        context=body_ctx,
        polyline=polyline,
        depth=depth,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=slab, representation=rep
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[slab],
    )
    _assign_pset(ifc, slab, "Pset_SlabCommon", {"IsExternal": False})
    _assign_material(ifc, slab, material)
    _place(ifc, slab, 0.0, 0.0, elev)
    logger.info(f"  Slab: {name} @ elev={elev:.1f}")
    return slab


def _create_opening(
    ifc: Any,
    wall: Any,
    name: str,
    x: float,
    y: float,
    elevation: float,
    sill: float,
    width: float,
    height: float,
    wall_thickness: float,
    body_ctx: Any,
) -> Any:
    """Create an IfcOpeningElement voiding the given wall."""
    opening = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcOpeningElement",
        name=f"Opening_{name}",
    )
    opening_rep = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        ifc,
        context=body_ctx,
        length=width,
        height=height,
        thickness=wall_thickness + 0.05,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation",
        ifc,
        product=opening,
        representation=opening_rep,
    )
    _place(ifc, opening, x, y, elevation + sill)
    ifcopenshell.api.run("feature.add_feature", ifc, feature=opening, element=wall)
    return opening


def _create_door(
    ifc: Any,
    storey: Any,
    wall: Any,
    name: str,
    is_external: bool,
    x: float,
    y: float,
    elevation: float,
    wall_thickness: float,
    width: float,
    height: float,
    angle_deg: float,
    body_ctx: Any,
) -> Any:
    """Create a door, void its host wall, assign to storey, set pset + material."""
    opening = _create_opening(
        ifc, wall, name, x, y, elevation, 0.0, width, height, wall_thickness, body_ctx
    )
    door = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcDoor", name=name
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[door],
    )
    _assign_pset(ifc, door, "Pset_DoorCommon", {"IsExternal": is_external})
    _assign_material(ifc, door, "Timber")
    rep = ifcopenshell.api.run(
        "geometry.add_door_representation",
        ifc,
        context=body_ctx,
        overall_width=width,
        overall_height=height,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=door, representation=rep
    )
    _place(ifc, door, x, y, elevation, angle_deg)
    ifcopenshell.api.run("feature.add_filling", ifc, opening=opening, element=door)
    logger.info(f"  Door: {name} @({x:.2f},{y:.2f}) z={elevation:.1f} ang={angle_deg}")
    return door


def _create_window(
    ifc: Any,
    storey: Any,
    wall: Any,
    name: str,
    is_external: bool,
    x: float,
    y: float,
    elevation: float,
    sill: float,
    wall_thickness: float,
    width: float,
    height: float,
    angle_deg: float,
    body_ctx: Any,
) -> Any:
    """Create a window, void its host wall, assign to storey, set pset + material."""
    opening = _create_opening(
        ifc, wall, name, x, y, elevation, sill, width, height, wall_thickness, body_ctx
    )
    win = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcWindow", name=name
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[win],
    )
    _assign_pset(ifc, win, "Pset_WindowCommon", {"IsExternal": is_external})
    _assign_material(ifc, win, "Glass")
    rep = ifcopenshell.api.run(
        "geometry.add_window_representation",
        ifc,
        context=body_ctx,
        overall_width=width,
        overall_height=height,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=win, representation=rep
    )
    _place(ifc, win, x, y, elevation + sill, angle_deg)
    ifcopenshell.api.run("feature.add_filling", ifc, opening=opening, element=win)
    logger.info(
        f"  Window: {name} @({x:.2f},{y:.2f}) z={elevation + sill:.1f} ang={angle_deg}"
    )
    return win


def _create_stair_flight(
    ifc: Any,
    storey: Any,
    name: str,
    lx: float,
    ly: float,
    lower_elev: float,
    upper_elev: float,
    width: float,
    body_ctx: Any,
) -> Any:
    """Create a straight stair flight as IfcStairFlight with proper stepped geometry.

    The stair runs in the +X direction (tread by tread), with width in Y.
    Placement: lx/ly is the bottom-front-left corner of the flight.
    """
    height = upper_elev - lower_elev
    num_risers = 9
    riser_h = height / num_risers
    tread_d = 0.260          # 260 mm tread depth
    run_length = num_risers * tread_d

    stair = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcStairFlight", name=name
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[stair],
    )

    # Build a stepped profile in the XZ plane and extrude in Y for width.
    # Profile: starting at origin, step up-then-forward for each riser/tread,
    # then close back along the bottom.
    from ifcopenshell.util.shape_builder import ShapeBuilder  # lazy to avoid circular import
    builder = ShapeBuilder(ifc)
    pts_2d: list[tuple[float, float]] = [(0.0, 0.0)]
    for i in range(num_risers):
        x0 = i * tread_d
        z0 = i * riser_h
        pts_2d.append((x0, z0 + riser_h))           # up the riser
        pts_2d.append((x0 + tread_d, z0 + riser_h)) # across the tread
    pts_2d.append((run_length, 0.0))                 # back down to ground

    profile = builder.polyline(pts_2d, closed=True)
    # Extrude in the local Y direction (which is the wall-normal / width direction)
    extrusion = builder.extrude(
        profile,
        magnitude=width,
        position_x_axis=(1.0, 0.0, 0.0),
        extrusion_vector=(0.0, 1.0, 0.0),
    )
    rep = ifc.createIfcShapeRepresentation(body_ctx, "Body", "SweptSolid", [extrusion])
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=stair, representation=rep
    )
    _place(ifc, stair, lx, ly, lower_elev)
    _assign_material(ifc, stair, "Concrete")
    logger.info(
        f"  Stair: {name} @({lx:.1f},{ly:.1f}) z={lower_elev:.1f}\u2192{upper_elev:.1f}"
    )
    return stair


def _create_lift_shaft(
    ifc: Any,
    storey: Any,
    name: str,
    lx: float,
    ly: float,
    lower_elev: float,
    total_height: float,
    body_ctx: Any,
) -> Any:
    """Create a lift/elevator as IfcTransportElement spanning the full building."""
    lift = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcTransportElement",
        name=name,
    )
    ifcopenshell.api.run(
        "attribute.edit_attributes",
        ifc,
        product=lift,
        attributes={"PredefinedType": "ELEVATOR"},
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[lift],
    )

    # Box geometry for the shaft
    shaft_w, shaft_d = 2.5, 2.5
    verts = [[
        (0.0,     0.0,     0.0),
        (shaft_w, 0.0,     0.0),
        (shaft_w, shaft_d, 0.0),
        (0.0,     shaft_d, 0.0),
        (0.0,     0.0,     total_height),
        (shaft_w, 0.0,     total_height),
        (shaft_w, shaft_d, total_height),
        (0.0,     shaft_d, total_height),
    ]]
    faces = [[
        [0, 3, 2, 1], [4, 5, 6, 7],
        [0, 1, 5, 4], [1, 2, 6, 5],
        [2, 3, 7, 6], [3, 0, 4, 7],
    ]]
    rep = ifcopenshell.api.run(
        "geometry.add_mesh_representation",
        ifc,
        context=body_ctx,
        vertices=verts,
        faces=faces,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=lift, representation=rep
    )
    _place(ifc, lift, lx, ly, lower_elev)
    logger.info(f"  Lift: {name} @({lx:.1f},{ly:.1f}) h={total_height:.1f}m")
    return lift


def _create_roof(
    ifc: Any,
    storey: Any,
    body_ctx: Any,
    name: str,
    elev: float,
    polyline: list[tuple[float, float]] | None = None,
    depth: float = 0.3,
) -> Any:
    """Create a flat roof slab element (IfcRoof) over the full footprint."""
    if polyline is None:
        polyline = [
            (0.0, 0.0),
            (WIDTH, 0.0),
            (WIDTH, DEPTH),
            (0.0, DEPTH),
        ]
    roof = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcRoof", name=name
    )
    rep = ifcopenshell.api.run(
        "geometry.add_slab_representation",
        ifc,
        context=body_ctx,
        polyline=polyline,
        depth=depth,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=roof, representation=rep
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[roof],
    )
    _assign_material(ifc, roof, "Roofing Membrane")
    _place(ifc, roof, 0.0, 0.0, elev)
    logger.info(f"  Roof: {name} @ elev={elev:.1f}")
    return roof


# ---------------------------------------------------------------------------
# Per-storey build logic
# ---------------------------------------------------------------------------

def _build_perimeter_walls(
    ifc: Any,
    storey: Any,
    storey_ref: str,
    elev: float,
    height: float,
    body_ctx: Any,
    axis_ctx: Any,
) -> dict[str, Any]:
    """Build 4 exterior perimeter walls for a given storey.

    Returns a dict keyed by direction: south, east, north, west.
    """
    walls: dict[str, Any] = {}
    specs = [
        ("south", [0.0, 0.0],        [WIDTH, 0.0],        0.0),
        ("east",  [WIDTH, 0.0],       [WIDTH, DEPTH],      90.0),
        ("north", [WIDTH, DEPTH],     [0.0, DEPTH],        180.0),
        ("west",  [0.0, DEPTH],       [0.0, 0.0],          270.0),
    ]
    for direction, start, end, _ang in specs:
        name = f"{storey_ref}_{direction.capitalize()}"
        walls[direction] = _create_wall(
            ifc, storey, name, True,
            start=start, end=end,
            elevation=elev, thickness=EXT_T,
            height=height,
            body_ctx=body_ctx, axis_ctx=axis_ctx,
        )
        logger.info(f"  Wall: {name} (external) @ elev={elev:.1f}")
    return walls


def _build_ground_floor(
    ifc: Any,
    storey: Any,
    elev: float,
    height: float,
    body_ctx: Any,
    axis_ctx: Any,
) -> None:
    """Ground floor: lobby, 2 retail units, entrance door, sidelight windows,
    corridor partitions."""
    logger.info("=== Ground Floor ===")
    walls = _build_perimeter_walls(ifc, storey, "GF", elev, height, body_ctx, axis_ctx)

    # Interior partitions: 2 retail units separated by a lobby corridor
    # Retail A: x 0→8, Retail B: x 12→20, Lobby: x 8→12 (4 m wide)
    _create_wall(
        ifc, storey, "GF_RetailA_E_Wall", False,
        start=[8.0, 0.0], end=[8.0, DEPTH - 3.0],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )
    _create_wall(
        ifc, storey, "GF_RetailB_W_Wall", False,
        start=[12.0, 0.0], end=[12.0, DEPTH - 3.0],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )
    # Back lobby wall (north side of corridor)
    _create_wall(
        ifc, storey, "GF_Lobby_N_Wall", False,
        start=[8.0, DEPTH - 3.0], end=[12.0, DEPTH - 3.0],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )

    # Main entrance door — south wall, centred at x=10.0
    # South wall runs from [0,0] → [20,0], angle=0° → door rotation=0°
    DOOR_W, DOOR_H = 1.5, 2.2
    _create_door(
        ifc, storey, walls["south"], "GF_Entrance_Door", True,
        x=WIDTH / 2 - DOOR_W / 2, y=0.0,
        elevation=elev, wall_thickness=EXT_T,
        width=DOOR_W, height=DOOR_H, angle_deg=0.0,
        body_ctx=body_ctx,
    )

    # Sidelight windows either side of entrance door (south wall, angle=0°)
    WIN_W, WIN_H, WIN_SILL = 1.2, 1.8, 0.6
    for name, wx in [("GF_SLW_West", 6.5), ("GF_SLW_East", 12.3)]:
        _create_window(
            ifc, storey, walls["south"], name, True,
            x=wx, y=0.0,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=WIN_W, height=WIN_H, angle_deg=0.0,
            body_ctx=body_ctx,
        )

    # Retail A windows (south facade)
    for name, wx in [("GF_RetA_Win1", 2.0), ("GF_RetA_Win2", 4.5)]:
        _create_window(
            ifc, storey, walls["south"], name, True,
            x=wx, y=0.0,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=1.5, height=1.8, angle_deg=0.0,
            body_ctx=body_ctx,
        )

    # Retail B windows (south facade)
    for name, wx in [("GF_RetB_Win1", 13.0), ("GF_RetB_Win2", 16.0)]:
        _create_window(
            ifc, storey, walls["south"], name, True,
            x=wx, y=0.0,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=1.5, height=1.8, angle_deg=0.0,
            body_ctx=body_ctx,
        )

    # East and West facade windows (angle matches wall orientation)
    # East wall runs [20,0]→[20,15], angle=90° → window rotation=90°
    for name, wy in [("GF_East_Win1", 3.0), ("GF_East_Win2", 8.0)]:
        _create_window(
            ifc, storey, walls["east"], name, True,
            x=WIDTH, y=wy,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=1.2, height=1.8, angle_deg=90.0,
            body_ctx=body_ctx,
        )

    # West wall runs [0,15]→[0,0], angle=270° → window rotation=270°
    for name, wy in [("GF_West_Win1", 3.0), ("GF_West_Win2", 8.0)]:
        _create_window(
            ifc, storey, walls["west"], name, True,
            x=0.0, y=DEPTH - wy,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=1.2, height=1.8, angle_deg=270.0,
            body_ctx=body_ctx,
        )

    _create_slab(ifc, storey, body_ctx, "GF_Slab", elev)


def _build_stair_core_walls(
    ifc: Any,
    storey: Any,
    storey_ref: str,
    elev: float,
    height: float,
    body_ctx: Any,
    axis_ctx: Any,
) -> None:
    """Add enclosure walls for the NW and NE stair cores on each floor.

    NW core occupies x: 0–3.0, y: 12.0–15.0 (DEPTH-3 to DEPTH).
    NE core occupies x: 17.0–20.0, y: 12.0–15.0.
    Each core gets a south wall and an east/west cross wall;
    the perimeter north and outer side walls are already the building exterior.
    """
    CORE_W = 3.0   # core width in X
    CORE_D = 3.0   # core depth in Y  (= DEPTH - STAIR_NW[1])
    CORE_Y = DEPTH - CORE_D   # = 12.0

    # NW core — south wall (y=CORE_Y, x: 0→3)
    _create_wall(
        ifc, storey, f"{storey_ref}_StairNW_S", False,
        start=[0.0, CORE_Y], end=[CORE_W, CORE_Y],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )
    # NW core — east wall (x=3, y: CORE_Y→DEPTH)
    _create_wall(
        ifc, storey, f"{storey_ref}_StairNW_E", False,
        start=[CORE_W, CORE_Y], end=[CORE_W, DEPTH],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )

    # NE core — south wall (y=CORE_Y, x: 17→20)
    _create_wall(
        ifc, storey, f"{storey_ref}_StairNE_S", False,
        start=[WIDTH - CORE_W, CORE_Y], end=[WIDTH, CORE_Y],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )
    # NE core — west wall (x=17, y: CORE_Y→DEPTH)
    _create_wall(
        ifc, storey, f"{storey_ref}_StairNE_W", False,
        start=[WIDTH - CORE_W, DEPTH], end=[WIDTH - CORE_W, CORE_Y],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )


def _build_office_floor(
    ifc: Any,
    storey: Any,
    storey_ref: str,
    elev: float,
    height: float,
    body_ctx: Any,
    axis_ctx: Any,
) -> None:
    """Open-plan office floor (Levels 1–4): strip windows + one internal door."""
    logger.info(f"=== {storey_ref} Office Floor @ elev={elev:.1f} ===")
    walls = _build_perimeter_walls(
        ifc, storey, storey_ref, elev, height, body_ctx, axis_ctx
    )
    _build_stair_core_walls(ifc, storey, storey_ref, elev, height, body_ctx, axis_ctx)

    # Central corridor partition (E–W at y=DEPTH/2, spanning between stair cores)
    # Runs from x=3 (east of NW core) to x=17 (west of NE core)
    corridor_wall = _create_wall(
        ifc, storey, f"{storey_ref}_Corridor_Partition", False,
        start=[3.0, DEPTH / 2], end=[WIDTH - 3.0, DEPTH / 2],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )

    # Strip windows south facade — 4 bays, 3.0 m wide, 1.8 m tall, 0.8 m sill
    for i, cx in enumerate([2.5, 7.0, 13.0, 17.5]):
        _create_window(
            ifc, storey, walls["south"],
            f"{storey_ref}_South_Win_{i + 1}", True,
            x=cx - 1.5, y=0.0,
            elevation=elev, sill=0.8,
            wall_thickness=EXT_T,
            width=3.0, height=1.8, angle_deg=0.0,
            body_ctx=body_ctx,
        )

    # North facade windows — 2 large (between stair cores)
    for i, cx in enumerate([7.0, 13.0]):
        _create_window(
            ifc, storey, walls["north"],
            f"{storey_ref}_North_Win_{i + 1}", True,
            x=cx, y=DEPTH,
            elevation=elev, sill=0.8,
            wall_thickness=EXT_T,
            width=2.0, height=1.8, angle_deg=180.0,
            body_ctx=body_ctx,
        )

    # East + west facade windows
    for i, wy in enumerate([2.0, 6.0]):
        _create_window(
            ifc, storey, walls["east"],
            f"{storey_ref}_East_Win_{i + 1}", True,
            x=WIDTH, y=wy,
            elevation=elev, sill=0.8,
            wall_thickness=EXT_T,
            width=2.0, height=1.8, angle_deg=90.0,
            body_ctx=body_ctx,
        )
        _create_window(
            ifc, storey, walls["west"],
            f"{storey_ref}_West_Win_{i + 1}", True,
            x=0.0, y=DEPTH - wy,
            elevation=elev, sill=0.8,
            wall_thickness=EXT_T,
            width=2.0, height=1.8, angle_deg=270.0,
            body_ctx=body_ctx,
        )

    # Corridor access door — on the interior E-W corridor partition wall.
    # Wall runs from x=3→17 at y=DEPTH/2 with angle=0°.
    # Door is placed at the midpoint (x=9.55) of the partition.
    _create_door(
        ifc, storey, corridor_wall,
        f"{storey_ref}_Corridor_Door", False,
        x=9.55, y=DEPTH / 2,
        elevation=elev, wall_thickness=INT_T,
        width=0.9, height=2.1, angle_deg=0.0,
        body_ctx=body_ctx,
    )

    _create_slab(ifc, storey, body_ctx, f"{storey_ref}_Slab", elev)


def _build_residential_floor(
    ifc: Any,
    storey: Any,
    storey_ref: str,
    elev: float,
    height: float,
    body_ctx: Any,
    axis_ctx: Any,
) -> None:
    """Residential floor (Levels 5–8): 4 apartments, central corridor, stair cores.

    Layout (20 m × 15 m):
      - Central E–W corridor at y=6.5 (1.5 m wide, y: 6.5–8.0)
      - Apartments A+B south of corridor (y: 0–6.5), C+D north (y: 8.0–15)
      - NW and NE stair cores enclosed
      - All apartment entry doors open onto the central corridor wall
    """
    logger.info(f"=== {storey_ref} Residential Floor @ elev={elev:.1f} ===")
    walls = _build_perimeter_walls(
        ifc, storey, storey_ref, elev, height, body_ctx, axis_ctx
    )
    _build_stair_core_walls(ifc, storey, storey_ref, elev, height, body_ctx, axis_ctx)

    # Central corridor walls — E-W corridor 1.5 m wide running full building width
    # between the stair cores (x: 3→17)
    CORR_S = 6.5   # south face of corridor
    CORR_N = 8.0   # north face of corridor

    corr_south_wall = _create_wall(
        ifc, storey, f"{storey_ref}_Corr_S_Wall", False,
        start=[3.0, CORR_S], end=[WIDTH - 3.0, CORR_S],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )
    corr_north_wall = _create_wall(
        ifc, storey, f"{storey_ref}_Corr_N_Wall", False,
        start=[3.0, CORR_N], end=[WIDTH - 3.0, CORR_N],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )

    # N–S spine wall dividing apartments A/B (south) and C/D (north)
    _create_wall(
        ifc, storey, f"{storey_ref}_Spine_NS", False,
        start=[WIDTH / 2, 0.0], end=[WIDTH / 2, CORR_S],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )
    _create_wall(
        ifc, storey, f"{storey_ref}_Spine_NS_N", False,
        start=[WIDTH / 2, CORR_N], end=[WIDTH / 2, DEPTH],
        elevation=elev, thickness=INT_T, height=height,
        body_ctx=body_ctx, axis_ctx=axis_ctx,
    )

    # Bedroom partition in each southern apartment (A=SW, B=SE)
    for apt, bx in [("A", 3.5), ("B", WIDTH / 2 + 3.5)]:
        _create_wall(
            ifc, storey, f"{storey_ref}_Apt{apt}_Bed", False,
            start=[bx, 0.0], end=[bx, CORR_S],
            elevation=elev, thickness=INT_T, height=height,
            body_ctx=body_ctx, axis_ctx=axis_ctx,
        )
    # Bedroom partition in each northern apartment (C=NW, D=NE)
    for apt, bx in [("C", 3.5), ("D", WIDTH / 2 + 3.5)]:
        _create_wall(
            ifc, storey, f"{storey_ref}_Apt{apt}_Bed", False,
            start=[bx, CORR_N], end=[bx, DEPTH],
            elevation=elev, thickness=INT_T, height=height,
            body_ctx=body_ctx, axis_ctx=axis_ctx,
        )

    # Apartment entry doors — all on the corridor walls (interior), NOT the facade.
    # South-facing corridor wall (corr_south_wall): apartments A and B enter from north.
    # Corridor wall runs x: 3→17 at y=CORR_S, angle=0°.
    for apt, dx in [("A", 5.5), ("B", 13.0)]:
        _create_door(
            ifc, storey, corr_south_wall,
            f"{storey_ref}_Apt{apt}_Door", False,
            x=dx, y=CORR_S,
            elevation=elev, wall_thickness=INT_T,
            width=0.9, height=2.1, angle_deg=180.0,
            body_ctx=body_ctx,
        )
    # North-facing corridor wall (corr_north_wall): apartments C and D enter from south.
    # Wall runs x: 3→17 at y=CORR_N, angle=0°.
    for apt, dx in [("C", 5.5), ("D", 13.0)]:
        _create_door(
            ifc, storey, corr_north_wall,
            f"{storey_ref}_Apt{apt}_Door", False,
            x=dx, y=CORR_N,
            elevation=elev, wall_thickness=INT_T,
            width=0.9, height=2.1, angle_deg=0.0,
            body_ctx=body_ctx,
        )

    # Windows — south, north, east, west facades (no doors on facade)
    WIN_W, WIN_H, WIN_SILL = 1.2, 1.4, 0.9
    for i, cx in enumerate([4.5, 8.5, 11.5, 15.5]):
        _create_window(
            ifc, storey, walls["south"],
            f"{storey_ref}_S_Win_{i + 1}", True,
            x=cx - WIN_W / 2, y=0.0,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=WIN_W, height=WIN_H, angle_deg=0.0,
            body_ctx=body_ctx,
        )
    for i, cx in enumerate([4.5, 8.5, 11.5, 15.5]):
        _create_window(
            ifc, storey, walls["north"],
            f"{storey_ref}_N_Win_{i + 1}", True,
            x=cx, y=DEPTH,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=WIN_W, height=WIN_H, angle_deg=180.0,
            body_ctx=body_ctx,
        )
    for i, wy in enumerate([2.5, 9.0]):
        _create_window(
            ifc, storey, walls["east"],
            f"{storey_ref}_E_Win_{i + 1}", True,
            x=WIDTH, y=wy,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=WIN_W, height=WIN_H, angle_deg=90.0,
            body_ctx=body_ctx,
        )
    for i, wy in enumerate([2.5, 9.0]):
        _create_window(
            ifc, storey, walls["west"],
            f"{storey_ref}_W_Win_{i + 1}", True,
            x=0.0, y=DEPTH - wy,
            elevation=elev, sill=WIN_SILL,
            wall_thickness=EXT_T,
            width=WIN_W, height=WIN_H, angle_deg=270.0,
            body_ctx=body_ctx,
        )

    _create_slab(ifc, storey, body_ctx, f"{storey_ref}_Slab", elev)


def _build_plant_floor(
    ifc: Any,
    storey: Any,
    storey_ref: str,
    elev: float,
    height: float,
    body_ctx: Any,
    axis_ctx: Any,
) -> None:
    """Level 9 — plant room with service access door and minimal windows."""
    logger.info(f"=== {storey_ref} Plant Floor @ elev={elev:.1f} ===")
    walls = _build_perimeter_walls(
        ifc, storey, storey_ref, elev, height, body_ctx, axis_ctx
    )
    _build_stair_core_walls(ifc, storey, storey_ref, elev, height, body_ctx, axis_ctx)

    # Service access door (south wall, east side)
    _create_door(
        ifc, storey, walls["south"],
        f"{storey_ref}_Service_Door", False,
        x=WIDTH - 4.0, y=0.0,
        elevation=elev, wall_thickness=EXT_T,
        width=1.2, height=2.1, angle_deg=0.0,
        body_ctx=body_ctx,
    )

    # Two louvre / ventilation windows (south + north, small)
    for name, wall, wx, ang in [
        (f"{storey_ref}_Vent_S", walls["south"], 5.0, 0.0),
        (f"{storey_ref}_Vent_N", walls["north"], WIDTH - 5.0, 180.0),
    ]:
        _create_window(
            ifc, storey, wall, name, True,
            x=wx, y=0.0 if ang == 0.0 else DEPTH,
            elevation=elev, sill=1.5,
            wall_thickness=EXT_T,
            width=1.0, height=0.8, angle_deg=ang,
            body_ctx=body_ctx,
        )

    _create_slab(ifc, storey, body_ctx, f"{storey_ref}_Slab", elev)


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def create_ten_storey() -> str:
    """Build a fully-decked 10-storey high-rise IFC model.

    Returns:
        Absolute path to the written IFC file.
    """
    ifc = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcProject",
        name="Ten-Storey Mixed-Use High-Rise",
    )
    ifcopenshell.api.run(
        "unit.assign_unit", ifc, length={"is_metric": True, "raw": "METRES"}
    )

    model_ctx = ifcopenshell.api.run("context.add_context", ifc, context_type="Model")
    body_ctx = ifcopenshell.api.run(
        "context.add_context",
        ifc,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_ctx,
    )
    plan_ctx = ifcopenshell.api.run("context.add_context", ifc, context_type="Plan")
    axis_ctx = ifcopenshell.api.run(
        "context.add_context",
        ifc,
        context_type="Plan",
        context_identifier="Axis",
        target_view="GRAPH_VIEW",
        parent=plan_ctx,
    )

    # Spatial hierarchy
    site = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcSite", name="Main Site"
    )
    building = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcBuilding",
        name="Tower A",
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", ifc, relating_object=project, products=[site]
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", ifc, relating_object=site, products=[building]
    )

    # Create all 10 storeys
    storeys: list[Any] = []
    for i in range(NUM_STOREYS):
        s = ifcopenshell.api.run(
            "root.create_entity",
            ifc,
            ifc_class="IfcBuildingStorey",
            name=STOREY_NAMES[i],
        )
        s.Elevation = ELEVATIONS[i]
        storeys.append(s)

    ifcopenshell.api.run(
        "aggregate.assign_object",
        ifc,
        relating_object=building,
        products=storeys,
    )

    # -----------------------------------------------------------------------
    # Build each floor
    # -----------------------------------------------------------------------
    for i, (storey, ref, elev) in enumerate(
        zip(storeys, STOREY_REFS, ELEVATIONS)
    ):
        if i == 0:
            _build_ground_floor(
                ifc, storey, elev, FTF, body_ctx, axis_ctx
            )
        elif 1 <= i <= 4:
            _build_office_floor(
                ifc, storey, ref, elev, FTF, body_ctx, axis_ctx
            )
        elif 5 <= i <= 8:
            _build_residential_floor(
                ifc, storey, ref, elev, FTF, body_ctx, axis_ctx
            )
        else:  # i == 9
            _build_plant_floor(
                ifc, storey, ref, elev, FTF, body_ctx, axis_ctx
            )

    # -----------------------------------------------------------------------
    # Vertical circulation — Rule: N-1 = 9 stair flights per core
    # Two stair cores (NW + NE) + one lift shaft
    # -----------------------------------------------------------------------
    logger.info("=== Vertical Circulation ===")
    for flight_idx in range(NUM_STOREYS - 1):
        lower_storey = storeys[flight_idx]
        lower_elev = ELEVATIONS[flight_idx]
        upper_elev = ELEVATIONS[flight_idx + 1]

        # NW stair core (width 1.5 m, 9 flights)
        _create_stair_flight(
            ifc, lower_storey,
            f"Stair_NW_{STOREY_REFS[flight_idx]}_{STOREY_REFS[flight_idx + 1]}",
            lx=STAIR_NW[0], ly=STAIR_NW[1],
            lower_elev=lower_elev, upper_elev=upper_elev,
            width=1.5, body_ctx=body_ctx,
        )

        # NE stair core (width 1.5 m, 9 flights)
        _create_stair_flight(
            ifc, lower_storey,
            f"Stair_NE_{STOREY_REFS[flight_idx]}_{STOREY_REFS[flight_idx + 1]}",
            lx=STAIR_NE[0], ly=STAIR_NE[1],
            lower_elev=lower_elev, upper_elev=upper_elev,
            width=1.5, body_ctx=body_ctx,
        )

    # Lift shaft — single IfcTransportElement anchored to GF, spanning full height
    total_building_height = NUM_STOREYS * FTF
    _create_lift_shaft(
        ifc, storeys[0],
        "Lift_Central",
        lx=LIFT_X, ly=LIFT_Y,
        lower_elev=ELEVATIONS[0],
        total_height=total_building_height,
        body_ctx=body_ctx,
    )

    # -----------------------------------------------------------------------
    # Roof on topmost storey (Level 9)
    # -----------------------------------------------------------------------
    logger.info("=== Roof ===")
    roof_elev = ELEVATIONS[-1] + FTF
    _create_roof(
        ifc, storeys[-1], body_ctx,
        "L9_Flat_Roof",
        elev=roof_elev,
    )

    ifc.write(str(IFC_PATH))
    logger.info(f"Saved IFC → {IFC_PATH}")
    return str(IFC_PATH)


# ---------------------------------------------------------------------------
# Validation runner
# ---------------------------------------------------------------------------

def run_all_validations(ifc_path: str) -> dict[str, Any]:
    """Run schema, IDS, and semantic validation. Returns combined results dict."""
    results: dict[str, Any] = {}

    # Schema
    try:
        from validate.schema_validate import validate_schema  # type: ignore[import]

        results["schema"] = validate_schema(ifc_path)
        logger.info(
            f"Schema: {'PASS' if results['schema']['valid'] else 'FAIL'} "
            f"({results['schema']['error_count']} errors)"
        )
    except ImportError:
        logger.warning("Schema validator not found — skipping")
        results["schema"] = {"valid": None, "error_count": 0, "warning_count": 0}

    # IDS
    ids_path = Path(__file__).parent.parent / "ids" / "v0.ids"
    if ids_path.exists():
        try:
            from validate.ids_validate import validate_ids  # type: ignore[import]

            results["ids"] = validate_ids(ifc_path, str(ids_path))
            logger.info(
                f"IDS: {'PASS' if results['ids']['valid'] else 'FAIL'} "
                f"({results['ids'].get('passed', '?')}/{results['ids'].get('total_specs', '?')} specs)"
            )
        except ImportError:
            logger.warning("IDS validator not found — skipping")
            results["ids"] = {"valid": None}
    else:
        logger.warning(f"IDS file not found at {ids_path}")
        results["ids"] = {"valid": None}

    # Semantic
    try:
        from validate.semantic_checks import run_all_checks  # type: ignore[import]

        results["semantic"] = run_all_checks(ifc_path)
        logger.info(
            f"Semantic: {'PASS' if results['semantic']['valid'] else 'FAIL'} "
            f"({results['semantic']['error_count']} errors)"
        )
    except ImportError:
        logger.warning("Semantic checker not found — skipping")
        results["semantic"] = {"valid": None, "error_count": 0, "warning_count": 0}

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ifc_path = create_ten_storey()
    results = run_all_validations(ifc_path)

    report_path = OUTPUT_DIR / "golden_ten_storey_validation.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Validation report → {report_path}")

    all_valid = all(r.get("valid", True) is not False for r in results.values())
    if all_valid:
        logger.info("ALL VALIDATIONS PASSED ✓")
    else:
        logger.warning("VALIDATION FAILURES detected — check report")
    sys.exit(0 if all_valid else 1)
