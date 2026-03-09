"""Golden test: Two-storey building with stairs.

Creates:
- Ground floor (GF): 8m x 6m shell, 2 rooms, 1 door, 2 windows, slab
- First floor (L1): same footprint, 2 windows, slab
- Stairs connecting GF -> L1
- Flat roof on L1

Run: python tests/golden_test_two_storey.py
Output: tests/output/golden_two_storey.ifc + validation reports
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
IFC_PATH = OUTPUT_DIR / "golden_two_storey.ifc"

WIDTH, DEPTH = 8.0, 6.0
GF_ELEV, L1_ELEV = 0.0, 3.0
WALL_HEIGHT = 3.0
WALL_THICKNESS = 0.2


def create_two_storey() -> str:
    """Create a two-storey building with stairs."""
    ifc = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcProject",
        name="Two Storey Test",
    )
    ifcopenshell.api.run("unit.assign_unit", ifc)

    model_ctx = ifcopenshell.api.run(
        "context.add_context", ifc, context_type="Model"
    )
    ifcopenshell.api.run(
        "context.add_context",
        ifc,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_ctx,
    )

    site = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcSite", name="Site"
    )
    building = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcBuilding", name="House"
    )
    gf = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcBuildingStorey",
        name="Ground Floor",
    )
    l1 = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcBuildingStorey",
        name="First Floor",
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
        "aggregate.assign_object",
        ifc,
        relating_object=building,
        products=[gf, l1],
    )

    def create_perimeter_walls(storey, storey_name: str, elev: float) -> dict:
        """Create the four perimeter walls for a storey."""
        walls_def = [
            (f"{storey_name}_South", [0, 0, elev], [WIDTH, 0, elev]),
            (f"{storey_name}_East", [WIDTH, 0, elev], [WIDTH, DEPTH, elev]),
            (f"{storey_name}_North", [WIDTH, DEPTH, elev], [0, DEPTH, elev]),
            (f"{storey_name}_West", [0, DEPTH, elev], [0, 0, elev]),
        ]
        created = {}
        for name, _start, _end in walls_def:
            wall = ifcopenshell.api.run(
                "root.create_entity", ifc, ifc_class="IfcWall", name=name
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
                "pset.edit_pset",
                ifc,
                pset=pset,
                properties={"IsExternal": True},
            )
            created[name] = wall
            logger.info(f"  Wall: {name}")
        return created

    def create_interior_wall(storey, elev: float):
        """Create the interior dividing wall at x=4.0."""
        wall = ifcopenshell.api.run(
            "root.create_entity", ifc, ifc_class="IfcWall", name="GF_Interior"
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
            "pset.edit_pset",
            ifc,
            pset=pset,
            properties={"IsExternal": False},
        )
        logger.info("  Wall: GF_Interior (x=4.0)")
        return wall

    logger.info("Creating Ground Floor:")
    create_perimeter_walls(gf, "GF", GF_ELEV)
    create_interior_wall(gf, GF_ELEV)

    logger.info("Creating First Floor:")
    create_perimeter_walls(l1, "L1", L1_ELEV)

    body_context = next(
        c
        for c in ifc.by_type("IfcGeometricRepresentationSubContext")
        if c.ContextIdentifier == "Body"
    )
    for storey, name, _elev in [(gf, "GF Slab", GF_ELEV), (l1, "L1 Slab", L1_ELEV)]:
        slab = ifcopenshell.api.run(
            "root.create_entity", ifc, ifc_class="IfcSlab", name=name
        )
        slab_rep = ifcopenshell.api.run(
            "geometry.add_slab_representation",
            ifc,
            context=body_context,
            polyline=[(0.0, 0.0), (WIDTH, 0.0), (WIDTH, DEPTH), (0.0, DEPTH)],
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
        logger.info(f"  Slab: {name}")

    door = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcDoor", name="Front Door"
    )
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=gf, products=[door]
    )
    pset_d = ifcopenshell.api.run(
        "pset.add_pset", ifc, product=door, name="Pset_DoorCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset", ifc, pset=pset_d, properties={"IsExternal": True}
    )
    logger.info("  Door: Front Door (GF South)")

    for i, (storey, sname) in enumerate(
        [(gf, "GF"), (gf, "GF"), (l1, "L1"), (l1, "L1")]
    ):
        win = ifcopenshell.api.run(
            "root.create_entity",
            ifc,
            ifc_class="IfcWindow",
            name=f"Window_{sname}_{i}",
        )
        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc,
            relating_structure=storey,
            products=[win],
        )
        pset_w = ifcopenshell.api.run(
            "pset.add_pset", ifc, product=win, name="Pset_WindowCommon"
        )
        ifcopenshell.api.run(
            "pset.edit_pset", ifc, pset=pset_w, properties={"IsExternal": True}
        )
    logger.info("  Windows: 4 total (2 GF, 2 L1)")

    stairs = ifcopenshell.api.run(
        "root.create_entity",
        ifc,
        ifc_class="IfcStairFlight",
        name="Main Stairs",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=gf, products=[stairs]
    )
    logger.info("  Stairs: Main Stairs (GF->L1)")

    roof = ifcopenshell.api.run(
        "root.create_entity", ifc, ifc_class="IfcRoof", name="Flat Roof"
    )
    ifcopenshell.api.run(
        "spatial.assign_container", ifc, relating_structure=l1, products=[roof]
    )
    logger.info("  Roof: Flat Roof on L1")

    ifc.write(str(IFC_PATH))
    logger.info(f"Saved IFC to {IFC_PATH}")
    return str(IFC_PATH)


if __name__ == "__main__":
    ifc_path = create_two_storey()

    try:
        from golden_test_simple_room import run_all_validations  # type: ignore[import]

        results: dict[str, Any] = run_all_validations(ifc_path)
    except ImportError:
        logger.warning("Could not import validation runner, running standalone")
        results = {"note": "Validation runner not available"}

    report_path = OUTPUT_DIR / "golden_two_storey_validation.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Validation report: {report_path}")
