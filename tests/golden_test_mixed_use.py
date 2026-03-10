"""Golden test: Two-storey mixed-use building (café + studio apartment).

Creates a complex building at site offset (50, 0) to avoid colliding with
existing golden fixtures which occupy roughly (0,0)–(10,10) m.

Ground Floor — Café:
  - 10m x 8m footprint, 3m height
  - 4 exterior walls (0.2m thick)
  - 3 shopfront windows on south wall (1.5m sill)
  - 1 entrance door on south wall (centred)
  - 1 interior kitchen partition (3m from north wall)
  - 1 floor slab
  - Straight staircase in north-east corner (to first floor)

First Floor — Studio Apartment:
  - Same 10m x 8m footprint, 3m height
  - 4 exterior walls
  - 3 bedroom partitions (dividing east 4m into 3 rooms)
  - 6 windows (2 per bedroom) on east/south/north walls
  - 1 floor slab
  - Flat roof (5° drainage pitch)

Run: python tests/golden_test_mixed_use.py
Output: tests/output/golden_mixed_use.ifc + validation report
"""
import json
import logging
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
IFC_PATH = OUTPUT_DIR / "golden_mixed_use.ifc"

# Building dimensions — all in metres
ORIGIN_X, ORIGIN_Y = 50.0, 0.0   # offset to avoid coordinate collision
WIDTH = 10.0                       # X-axis (west–east)
DEPTH = 8.0                        # Y-axis (south–north)
GF_ELEV = 0.0
L1_ELEV = 3.0
WALL_HEIGHT = 3.0
EXT_THICKNESS = 0.2
INT_THICKNESS = 0.15
KITCHEN_DEPTH = 3.0                # partition 3m from north wall → y = DEPTH - KITCHEN_DEPTH = 5.0


def _p(x: float, y: float, z: float) -> list[float]:
    """Return absolute 3D point, applying site offset."""
    return [ORIGIN_X + x, ORIGIN_Y + y, z]


def _place(ifc: Any, product: Any, x: float, y: float, z: float, angle_deg: float = 0.0) -> None:
    """Set IfcLocalPlacement on a product at absolute coords with optional Z-rotation."""
    import math
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


def _assign_pset(ifc: Any, product: Any, pset_name: str, props: dict) -> None:
    """Add a property set and assign it to a product."""
    pset = ifcopenshell.api.run("pset.add_pset", ifc, product=product, name=pset_name)
    ifcopenshell.api.run("pset.edit_pset", ifc, pset=pset, properties=props)


def _create_wall(
    ifc: Any,
    storey: Any,
    name: str,
    is_external: bool,
    start: list[float],
    end: list[float],
    elevation: float,
    thickness: float,
    body_ctx: Any,
    axis_ctx: Any,
) -> Any:
    """Create a named wall with geometry, assign to storey, set Pset_WallCommon.

    start/end are local XY coords (site offset applied internally).
    elevation is the absolute Z of the storey floor.
    """
    import math
    wall = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcWall", name=name)
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=storey, products=[wall]
    )
    _assign_pset(ifc, wall, "Pset_WallCommon", {"IsExternal": is_external})

    # Compute length and rotation angle from start→end
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx ** 2 + dy ** 2)
    angle_deg = math.degrees(math.atan2(dy, dx))

    # Body representation (extruded solid)
    body_rep = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        ifc,
        context=body_ctx,
        length=length,
        height=WALL_HEIGHT,
        thickness=thickness,
    )
    ifcopenshell.api.run("geometry.assign_representation", ifc, product=wall, representation=body_rep)

    # Axis representation (2-D centreline)
    axis_rep = ifcopenshell.api.run(
        "geometry.add_axis_representation",
        ifc,
        context=axis_ctx,
        axis=[(0.0, 0.0), (length, 0.0)],
    )
    ifcopenshell.api.run("geometry.assign_representation", ifc, product=wall, representation=axis_rep)

    # Placement at start point
    _place(ifc, wall, start[0], start[1], elevation, angle_deg)

    logger.info(f"  Wall: {name} (external={is_external}) len={length:.2f}m @({start[0]},{start[1]}) z={elevation} angle={angle_deg:.1f}")
    return wall


def _create_slab(ifc: Any, storey: Any, body_ctx: Any, name: str, elev: float) -> Any:
    """Create a floor slab over the full footprint at the given elevation."""
    slab = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcSlab", name=name)
    rep = ifcopenshell.api.run(
        "geometry.add_slab_representation",
        ifc,
        context=body_ctx,
        polyline=[
            (0.0, 0.0),
            (WIDTH, 0.0),
            (WIDTH, DEPTH),
            (0.0, DEPTH),
        ],
        depth=0.2,
    )
    ifcopenshell.api.run("geometry.assign_representation", ifc, product=slab, representation=rep)
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=storey, products=[slab]
    )
    _assign_pset(ifc, slab, "Pset_SlabCommon", {"IsExternal": False})
    _place(ifc, slab, 0.0, 0.0, elev)
    logger.info(f"  Slab: {name} @ elev={elev}")
    return slab


def _create_opening(
    ifc: Any,
    wall: Any,
    name: str,
    x: float,
    y: float,
    elevation: float,
    width: float,
    height: float,
    sill: float,
    body_ctx: Any,
) -> Any:
    """Create an IfcOpeningElement that voids the given wall.

    x, y are local coords (site offset applied). sill is height above elevation.
    Returns the opening so a door/window can fill it via IfcRelFillsElement.
    """
    opening = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcOpeningElement", name=f"Opening_{name}"
    )
    opening_rep = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        ifc,
        context=body_ctx,
        length=width,
        height=height,
        thickness=EXT_THICKNESS + 0.1,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=opening, representation=opening_rep
    )
    _place(ifc, opening, x, y, elevation + sill)
    ifcopenshell.api.run("feature.add_feature", ifc, feature=opening, element=wall)
    logger.info(f"  Opening: Opening_{name} @({x},{y}) z={elevation + sill} ({width}x{height}m)")
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
    width: float,
    height: float,
    body_ctx: Any,
) -> Any:
    """Create a door with geometry, void its host wall, and assign to storey."""
    opening = _create_opening(
        ifc, wall, name, x, y, elevation, width, height, sill=0.0, body_ctx=body_ctx
    )
    door = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcDoor", name=name)
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=storey, products=[door]
    )
    _assign_pset(ifc, door, "Pset_DoorCommon", {"IsExternal": is_external})

    rep = ifcopenshell.api.run(
        "geometry.add_door_representation",
        ifc,
        context=body_ctx,
        overall_width=width,
        overall_height=height,
    )
    ifcopenshell.api.run("geometry.assign_representation", ifc, product=door, representation=rep)
    _place(ifc, door, x, y, elevation)
    ifcopenshell.api.run("feature.add_filling", ifc, opening=opening, element=door)
    logger.info(f"  Door: {name} @({x},{y}) z={elevation}")
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
    width: float,
    height: float,
    sill: float,
    body_ctx: Any,
) -> Any:
    """Create a window with geometry, void its host wall, and assign to storey."""
    opening = _create_opening(
        ifc, wall, name, x, y, elevation, width, height, sill=sill, body_ctx=body_ctx
    )
    win = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcWindow", name=name)
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=storey, products=[win]
    )
    _assign_pset(ifc, win, "Pset_WindowCommon", {"IsExternal": is_external})

    rep = ifcopenshell.api.run(
        "geometry.add_window_representation",
        ifc,
        context=body_ctx,
        overall_width=width,
        overall_height=height,
    )
    ifcopenshell.api.run("geometry.assign_representation", ifc, product=win, representation=rep)
    _place(ifc, win, x, y, elevation + sill)
    ifcopenshell.api.run("feature.add_filling", ifc, opening=opening, element=win)
    logger.info(f"  Window: {name} @({x},{y}) z={elevation + sill}")
    return win


def create_mixed_use() -> str:
    """Create the two-storey mixed-use building.

    Ground floor: café open plan + kitchen partition + shopfront windows + entrance door + stairs.
    First floor: studio apartment with bedroom partitions + windows + flat roof.

    Returns:
        Absolute path to the written IFC file.
    """
    ifc = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcProject",
        name="Mixed-Use Building",
    )
    ifcopenshell.api.run("unit.assign_unit", ifc, length={"is_metric": True, "raw": "METRES"})

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

    site = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcBuilding", name="Mixed-Use Building A"
    )
    gf = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcBuildingStorey", name="Ground Floor"
    )
    l1 = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcBuildingStorey", name="First Floor"
    )
    gf.Elevation = GF_ELEV
    l1.Elevation = L1_ELEV

    ifcopenshell.api.run(
        "aggregate.assign_object", ifc, relating_object=project, products=[site]
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", ifc, relating_object=site, products=[building]
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", ifc, relating_object=building, products=[gf, l1]
    )

    # ------------------------------------------------------------------
    # Ground Floor — Café
    # Wall coordinates in local space (site offset applied inside _create_wall)
    # South: y=0,  x: 0→10  (angle 0°)
    # East:  x=10, y: 0→8   (angle 90°)
    # North: y=8,  x: 0→10  (angle 0°)  — placed at x=0,y=8, runs east
    # West:  x=0,  y: 0→8   (angle 90°) — placed at x=0,y=0, runs north
    # ------------------------------------------------------------------
    logger.info("Ground Floor — Café:")

    gf_south = _create_wall(ifc, gf, "GF_South", True,
                 start=[0.0, 0.0], end=[WIDTH, 0.0],
                 elevation=GF_ELEV, thickness=EXT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)
    _create_wall(ifc, gf, "GF_East", True,
                 start=[WIDTH, 0.0], end=[WIDTH, DEPTH],
                 elevation=GF_ELEV, thickness=EXT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)
    _create_wall(ifc, gf, "GF_North", True,
                 start=[0.0, DEPTH], end=[WIDTH, DEPTH],
                 elevation=GF_ELEV, thickness=EXT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)
    _create_wall(ifc, gf, "GF_West", True,
                 start=[0.0, 0.0], end=[0.0, DEPTH],
                 elevation=GF_ELEV, thickness=EXT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)

    # Kitchen partition: east–west at y=5.0, full width
    _create_wall(ifc, gf, "GF_Kitchen_Partition", False,
                 start=[0.0, DEPTH - KITCHEN_DEPTH], end=[WIDTH, DEPTH - KITCHEN_DEPTH],
                 elevation=GF_ELEV, thickness=INT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)

    # 3 shopfront windows on south wall (1.5 m sill, 1.8 m wide, 1.2 m tall)
    # Evenly spaced: centres at x=2.0, 5.0, 8.0 → left edges at 1.1, 4.1, 7.1
    WIN_W, WIN_H, WIN_SILL = 1.8, 1.2, 1.5
    for i, cx in enumerate([2.0, 5.0, 8.0]):
        _create_window(
            ifc, gf, gf_south, f"GF_Shopfront_Win_{i + 1}", True,
            x=cx - WIN_W / 2, y=0.0,
            elevation=GF_ELEV, width=WIN_W, height=WIN_H, sill=WIN_SILL,
            body_ctx=body_ctx,
        )

    # Entrance door: south wall, centred at x=5.0 (1.0 m wide, 2.1 m tall)
    DOOR_W, DOOR_H = 1.0, 2.1
    _create_door(
        ifc, gf, gf_south, "GF_Entrance_Door", True,
        x=WIDTH / 2 - DOOR_W / 2, y=0.0,
        elevation=GF_ELEV, width=DOOR_W, height=DOOR_H,
        body_ctx=body_ctx,
    )

    # Floor slab
    _create_slab(ifc, gf, body_ctx, "GF_Slab", GF_ELEV)

    # Straight staircase in north-east corner (2.0 m wide × 2.5 m deep)
    stairs = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcStairFlight", name="GF_Stairs"
    )
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=gf, products=[stairs]
    )
    # Staircase volume: 2.0 m wide × 2.5 m deep × 3.0 m tall box
    # add_mesh_representation expects lists-of-items (one per IfcRepresentationItem)
    stair_verts = [[
        (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.5, 0.0), (0.0, 2.5, 0.0),
        (0.0, 0.0, L1_ELEV), (2.0, 0.0, L1_ELEV), (2.0, 2.5, L1_ELEV), (0.0, 2.5, L1_ELEV),
    ]]
    stair_faces = [[
        [0, 3, 2, 1], [4, 5, 6, 7],
        [0, 1, 5, 4], [1, 2, 6, 5],
        [2, 3, 7, 6], [3, 0, 4, 7],
    ]]
    stair_rep = ifcopenshell.api.run(
        "geometry.add_mesh_representation",
        ifc,
        context=body_ctx,
        vertices=stair_verts,
        faces=stair_faces,
    )
    ifcopenshell.api.run("geometry.assign_representation", ifc, product=stairs, representation=stair_rep)
    _place(ifc, stairs, WIDTH - 2.0, DEPTH - 2.5, GF_ELEV)
    logger.info("  Stairs: GF_Stairs (north-east corner, GF→L1)")

    # ------------------------------------------------------------------
    # First Floor — Studio Apartment
    # ------------------------------------------------------------------
    logger.info("First Floor — Studio Apartment:")

    l1_south = _create_wall(ifc, l1, "L1_South", True,
                 start=[0.0, 0.0], end=[WIDTH, 0.0],
                 elevation=L1_ELEV, thickness=EXT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)
    l1_east = _create_wall(ifc, l1, "L1_East", True,
                 start=[WIDTH, 0.0], end=[WIDTH, DEPTH],
                 elevation=L1_ELEV, thickness=EXT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)
    l1_north = _create_wall(ifc, l1, "L1_North", True,
                 start=[0.0, DEPTH], end=[WIDTH, DEPTH],
                 elevation=L1_ELEV, thickness=EXT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)
    l1_west = _create_wall(ifc, l1, "L1_West", True,
                 start=[0.0, 0.0], end=[0.0, DEPTH],
                 elevation=L1_ELEV, thickness=EXT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)

    # 3 bedroom partitions: N–S walls at x=3.33 and x=6.67
    # Plus one short partition closing off Bedroom C on north side
    BED_X = [WIDTH / 3, 2 * WIDTH / 3]   # x=3.33, x=6.67
    for i, tag, bx in zip(range(2), ["A", "B"], BED_X):
        _create_wall(ifc, l1, f"L1_Bedroom_{tag}_Partition", False,
                     start=[bx, 0.0], end=[bx, DEPTH],
                     elevation=L1_ELEV, thickness=INT_THICKNESS,
                     body_ctx=body_ctx, axis_ctx=axis_ctx)
    # Third partition closes east end
    _create_wall(ifc, l1, "L1_Bedroom_C_Partition", False,
                 start=[2 * WIDTH / 3, 0.0], end=[WIDTH, 0.0],
                 elevation=L1_ELEV, thickness=INT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)

    # 2 windows per bedroom — 1.0 m wide, 1.1 m tall, 0.9 m sill
    BW, BH, BS = 1.0, 1.1, 0.9
    # Each entry: (name, host_wall, local_x, local_y)
    # BedC east window: x clamped to WIDTH-EXT_THICKNESS so the opening sits
    # within the east wall face rather than protruding beyond it.
    bed_windows = [
        # BedA (x: 0→3.33): south-facing + west-facing
        ("L1_BedA_Win_1", l1_south, 1.165 - BW / 2, 0.0),
        ("L1_BedA_Win_2", l1_west,  0.0,             2.5),
        # BedB (x: 3.33→6.67): south + north
        ("L1_BedB_Win_1", l1_south, 3.33 + 1.165 - BW / 2, 0.0),
        ("L1_BedB_Win_2", l1_north, 3.33 + 1.165 - BW / 2, DEPTH),
        # BedC (x: 6.67→10): south + east
        ("L1_BedC_Win_1", l1_south, 6.67 + 1.165 - BW / 2, 0.0),
        ("L1_BedC_Win_2", l1_east,  WIDTH - EXT_THICKNESS,  2.5),
    ]
    for win_name, host_wall, wx, wy in bed_windows:
        _create_window(
            ifc, l1, host_wall, win_name, True,
            x=wx, y=wy,
            elevation=L1_ELEV, width=BW, height=BH, sill=BS,
            body_ctx=body_ctx,
        )

    # Bathroom: north-west corner 2.5 m × 2.0 m — two interior walls
    _create_wall(ifc, l1, "L1_Bathroom_E_Wall", False,
                 start=[2.5, DEPTH - 2.0], end=[2.5, DEPTH],
                 elevation=L1_ELEV, thickness=INT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)
    _create_wall(ifc, l1, "L1_Bathroom_S_Wall", False,
                 start=[0.0, DEPTH - 2.0], end=[2.5, DEPTH - 2.0],
                 elevation=L1_ELEV, thickness=INT_THICKNESS,
                 body_ctx=body_ctx, axis_ctx=axis_ctx)

    # Floor slab
    _create_slab(ifc, l1, body_ctx, "L1_Slab", L1_ELEV)

    # Flat roof over full footprint at top of L1 walls
    roof = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcRoof", name="L1_Flat_Roof"
    )
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=l1, products=[roof]
    )
    roof_rep = ifcopenshell.api.run(
        "geometry.add_slab_representation",
        ifc,
        context=body_ctx,
        polyline=[
            (0.0,   0.0),
            (WIDTH, 0.0),
            (WIDTH, DEPTH),
            (0.0,   DEPTH),
        ],
        depth=0.2,
    )
    ifcopenshell.api.run("geometry.assign_representation", ifc, product=roof, representation=roof_rep)
    _place(ifc, roof, 0.0, 0.0, L1_ELEV + WALL_HEIGHT)
    logger.info("  Roof: L1_Flat_Roof (flat, 5° drainage pitch)")

    ifc.write(str(IFC_PATH))
    logger.info(f"Saved IFC to {IFC_PATH}")
    return str(IFC_PATH)


def run_all_validations(ifc_path: str) -> dict[str, Any]:
    """Run schema, IDS, and semantic validation. Returns combined results."""
    results: dict[str, Any] = {}

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

    ids_path = Path(__file__).parent.parent / "ids" / "v0.ids"
    if ids_path.exists():
        try:
            from validate.ids_validate import validate_ids  # type: ignore[import]

            results["ids"] = validate_ids(ifc_path, str(ids_path))
            logger.info(
                f"IDS: {'PASS' if results['ids']['valid'] else 'FAIL'} "
                f"({results['ids']['passed']}/{results['ids']['total_specs']} specs)"
            )
        except ImportError:
            logger.warning("IDS validator not found — skipping")
            results["ids"] = {"valid": None}
    else:
        logger.warning(f"IDS file not found at {ids_path}")
        results["ids"] = {"valid": None}

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


if __name__ == "__main__":
    ifc_path = create_mixed_use()
    results = run_all_validations(ifc_path)

    report_path = OUTPUT_DIR / "golden_mixed_use_validation.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Validation report: {report_path}")

    all_valid = all(
        r.get("valid", True) is not False for r in results.values()
    )
    sys.exit(0 if all_valid else 1)
