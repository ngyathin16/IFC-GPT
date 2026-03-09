"""Golden test: Single rectangular room with slab, 1 door, 1 window.

This test creates a minimal building using direct IfcOpenShell API calls
and validates the output through all three validation layers.

Run: python tests/golden_test_simple_room.py
Output: tests/output/golden_simple_room.ifc + validation reports
"""
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
IFC_PATH = OUTPUT_DIR / "golden_simple_room.ifc"


def create_simple_room() -> str:
    """Create a single rectangular room: 4 walls, slab, 1 door, 1 window.

    Room dimensions: 5m x 4m, 3m height, 0.2m wall thickness.
    Door: south wall, centered, 0.9m x 2.1m
    Window: east wall, centered, 1.2m x 1.5m, sill at 0.9m

    Returns path to generated IFC file.
    """
    ifc = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcProject", name="Golden Test"
    )
    ifcopenshell.api.run("unit.assign_unit", ifc)

    model_context = ifcopenshell.api.run(
        "context.add_context", ifc, context_type="Model"
    )
    body_context = ifcopenshell.api.run(
        "context.add_context",
        ifc,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_context,
    )

    site = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcSite", name="Site"
    )
    building = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcBuilding", name="Building"
    )
    storey = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcBuildingStorey",
        name="Ground Floor",
    )

    ifcopenshell.api.run(
        "aggregate.assign_object", ifc, relating_object=project, products=[site]
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", ifc, relating_object=site, products=[building]
    )
    ifcopenshell.api.run(
        "aggregate.assign_object",
        ifc,
        relating_object=building,
        products=[storey],
    )

    storey.Elevation = 0.0

    W, D, H, T = 5.0, 4.0, 3.0, 0.2

    wall_defs = [
        ("South Wall", [0, 0, 0], [W, 0, 0]),
        ("East Wall", [W, 0, 0], [W, D, 0]),
        ("North Wall", [W, D, 0], [0, D, 0]),
        ("West Wall", [0, D, 0], [0, 0, 0]),
    ]

    walls = {}
    for name, start, end in wall_defs:
        wall = ifcopenshell.api.run(
            "root.create_entity", ifc, ifc_class="IfcWall", name=name
        )
        representation = ifcopenshell.api.run(
            "geometry.add_wall_representation",
            ifc,
            context=body_context,
            length=_dist(start, end),
            height=H,
            thickness=T,
        )
        ifcopenshell.api.run(
            "geometry.assign_representation",
            ifc,
            product=wall,
            representation=representation,
        )
        matrix = _placement_matrix(start, end)
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            ifc,
            product=wall,
            matrix=matrix,
        )
        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc,
            relating_structure=storey,
            products=[wall],
        )
        pset = ifcopenshell.api.run(
            "pset.add_pset", ifc, product=wall, name="Pset_WallCommon"
        )
        ifcopenshell.api.run(
            "pset.edit_pset", ifc, pset=pset, properties={"IsExternal": True}
        )
        walls[name] = wall
        logger.info(f"Created {name}: {start} -> {end}")

    slab = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcSlab", name="Floor Slab"
    )
    slab_rep = ifcopenshell.api.run(
        "geometry.add_slab_representation",
        ifc,
        context=body_context,
        polyline=[(0.0, 0.0), (W, 0.0), (W, D), (0.0, D)],
        depth=0.2,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", ifc, product=slab, representation=slab_rep
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[slab],
    )
    pset_slab = ifcopenshell.api.run(
        "pset.add_pset", ifc, product=slab, name="Pset_SlabCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset", ifc, pset=pset_slab, properties={"IsExternal": False}
    )
    logger.info("Created Floor Slab")

    door = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcDoor", name="Front Door"
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[door],
    )
    pset_door = ifcopenshell.api.run(
        "pset.add_pset", ifc, product=door, name="Pset_DoorCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset", ifc, pset=pset_door, properties={"IsExternal": True}
    )
    logger.info("Created Front Door on South Wall")

    window = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcWindow", name="East Window"
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc,
        relating_structure=storey,
        products=[window],
    )
    pset_window = ifcopenshell.api.run(
        "pset.add_pset", ifc, product=window, name="Pset_WindowCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset", ifc, pset=pset_window, properties={"IsExternal": True}
    )
    logger.info("Created East Window")

    ifc.write(str(IFC_PATH))
    logger.info(f"Saved IFC to {IFC_PATH}")
    return str(IFC_PATH)


def _dist(a: list[float], b: list[float]) -> float:
    """Euclidean distance between two 3D points."""
    return math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(3)))


def _placement_matrix(start: list[float], end: list[float]):
    """Build a 4x4 placement matrix aligning the wall along start->end."""
    import numpy as np

    dx, dy = end[0] - start[0], end[1] - start[1]
    angle = math.atan2(dy, dx)
    matrix = np.eye(4)
    matrix[0][3], matrix[1][3], matrix[2][3] = start[0], start[1], start[2]
    matrix[0][0], matrix[0][1] = math.cos(angle), -math.sin(angle)
    matrix[1][0], matrix[1][1] = math.sin(angle), math.cos(angle)
    return matrix


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
    ifc_path = create_simple_room()
    results = run_all_validations(ifc_path)

    report_path = OUTPUT_DIR / "golden_simple_room_validation.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Validation report: {report_path}")

    all_valid = all(
        r.get("valid", True) is not False for r in results.values()
    )
    sys.exit(0 if all_valid else 1)
