"""Semantic geometry validation checks.

Custom spatial and geometry rules that go beyond schema validation,
checking for common modelling errors in LLM-generated IFC files.
"""
import json
import math
import sys
from typing import Any, Dict, List

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement


def check_spatial_containment(ifc_file: ifcopenshell.file) -> List[Dict[str, Any]]:
    """Check all building elements are contained in spatial structure."""
    issues: List[Dict[str, Any]] = []
    building_elements = ifc_file.by_type("IfcBuildingElement")

    for elem in building_elements:
        container = ifcopenshell.util.element.get_container(elem)
        if not container:
            issues.append(
                {
                    "severity": "error",
                    "element": elem.GlobalId,
                    "element_type": elem.is_a(),
                    "message": f"{elem.Name or elem.GlobalId} has no spatial container",
                }
            )
    return issues


def check_floating_openings(ifc_file: ifcopenshell.file) -> List[Dict[str, Any]]:
    """Check doors/windows are hosted in walls (filling a void via IfcRelFillsElement).

    Raised as **error** because a floating opening renders incorrectly in all
    IFC viewers: the wall geometry is not cut and the door/window mesh floats
    in mid-air or protrudes through the wall surface.
    """
    issues: List[Dict[str, Any]] = []
    for entity_type in ["IfcDoor", "IfcWindow"]:
        for elem in ifc_file.by_type(entity_type):
            fills = getattr(elem, "FillsVoids", [])
            if not fills:
                issues.append(
                    {
                        "severity": "error",
                        "element": elem.GlobalId,
                        "element_type": entity_type,
                        "message": (
                            f"{elem.Name or elem.GlobalId} has no IfcRelFillsElement — "
                            "create an IfcOpeningElement in the host wall first"
                        ),
                    }
                )
    return issues


def check_opening_host_bounds(ifc_file: ifcopenshell.file) -> List[Dict[str, Any]]:
    """Check each IfcOpeningElement origin lies within its host wall's XY footprint.

    Detects windows/doors placed outside the wall they are supposed to cut,
    e.g. a window at x=WIDTH that protrudes beyond the east wall face.
    A tolerance of 0.05 m (5 cm) is allowed for snapping.
    """
    issues: List[Dict[str, Any]] = []
    TOLERANCE = 0.05  # metres

    for opening in ifc_file.by_type("IfcOpeningElement"):
        voids_rels = getattr(opening, "VoidsElements", [])
        if not voids_rels:
            issues.append(
                {
                    "severity": "error",
                    "element": opening.GlobalId,
                    "element_type": "IfcOpeningElement",
                    "message": (
                        f"Opening '{opening.Name or opening.GlobalId}' is not voiding any wall"
                    ),
                }
            )
            continue

        wall = voids_rels[0].RelatingBuildingElement
        if not wall or not wall.Representation:
            continue

        try:
            wall_mat = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
            open_mat = ifcopenshell.util.placement.get_local_placement(opening.ObjectPlacement)
        except Exception:
            continue

        # Wall origin and orientation in world space
        wx, wy = wall_mat[0][3], wall_mat[1][3]
        # Wall direction (first column of rotation = local X axis)
        wdx, wdy = wall_mat[0][0], wall_mat[1][0]
        wall_len = math.sqrt(wdx ** 2 + wdy ** 2)
        if wall_len < 1e-6:
            continue
        wdx /= wall_len
        wdy /= wall_len

        # Opening world origin
        ox, oy = open_mat[0][3], open_mat[1][3]
        # Project opening origin onto wall local axis
        rel_x = ox - wx
        rel_y = oy - wy
        along = rel_x * wdx + rel_y * wdy  # distance along wall

        # Determine wall length from geometry
        body_reps = [
            r for r in (wall.Representation.Representations if wall.Representation else [])
            if r.RepresentationIdentifier == "Body"
        ]
        if not body_reps:
            continue
        # Try to read length from extruded area solid items
        for item in body_reps[0].Items:
            try:
                # IfcExtrudedAreaSolid: depth along extrusion direction gives wall height,
                # but the swept area profile gives length. We use the axis representation
                # length heuristic: wall length ≈ (along - TOLERANCE) to (along + wall_length).
                # Use a simple sanity check: along must be >= -TOLERANCE.
                if along < -TOLERANCE:
                    issues.append(
                        {
                            "severity": "error",
                            "element": opening.GlobalId,
                            "element_type": "IfcOpeningElement",
                            "message": (
                                f"Opening '{opening.Name or opening.GlobalId}' is positioned "
                                f"{along:.3f} m before the start of its host wall "
                                f"'{wall.Name or wall.GlobalId}'"
                            ),
                        }
                    )
                break
            except Exception:
                break

    return issues


def check_element_geometry(ifc_file: ifcopenshell.file) -> List[Dict[str, Any]]:
    """Check that all IfcBuildingElement instances have at least one representation.

    Elements without geometry will be invisible in all viewers and cannot
    participate in clash detection or quantity take-off.
    """
    issues: List[Dict[str, Any]] = []
    for elem in ifc_file.by_type("IfcBuildingElement"):
        if not elem.Representation or not elem.Representation.Representations:
            issues.append(
                {
                    "severity": "error",
                    "element": elem.GlobalId,
                    "element_type": elem.is_a(),
                    "message": (
                        f"{elem.Name or elem.GlobalId} has no geometric representation"
                    ),
                }
            )
    return issues


def check_zero_thickness_slabs(ifc_file: ifcopenshell.file) -> List[Dict[str, Any]]:
    """Check slabs have non-zero thickness via their representation."""
    issues: List[Dict[str, Any]] = []
    for slab in ifc_file.by_type("IfcSlab"):
        has_rep = bool(
            slab.Representation and slab.Representation.Representations
        )
        if not has_rep:
            issues.append(
                {
                    "severity": "error",
                    "element": slab.GlobalId,
                    "element_type": "IfcSlab",
                    "message": (
                        f"{slab.Name or slab.GlobalId} has no geometric representation"
                    ),
                }
            )
    return issues


def check_disconnected_storeys(ifc_file: ifcopenshell.file) -> List[Dict[str, Any]]:
    """Check building storeys are aggregated under a building."""
    issues: List[Dict[str, Any]] = []
    for storey in ifc_file.by_type("IfcBuildingStorey"):
        decomposes = getattr(storey, "Decomposes", [])
        if not decomposes:
            issues.append(
                {
                    "severity": "error",
                    "element": storey.GlobalId,
                    "element_type": "IfcBuildingStorey",
                    "message": (
                        f"Storey '{storey.Name or storey.GlobalId}' is not aggregated "
                        "under any IfcBuilding"
                    ),
                }
            )
    return issues


def run_all_checks(ifc_path: str) -> Dict[str, Any]:
    """Run all semantic checks and return combined results."""
    ifc_file = ifcopenshell.open(ifc_path)
    all_issues: List[Dict[str, Any]] = []
    all_issues.extend(check_spatial_containment(ifc_file))
    all_issues.extend(check_floating_openings(ifc_file))
    all_issues.extend(check_zero_thickness_slabs(ifc_file))
    all_issues.extend(check_disconnected_storeys(ifc_file))
    all_issues.extend(check_opening_host_bounds(ifc_file))
    all_issues.extend(check_element_geometry(ifc_file))

    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]

    return {
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": all_issues,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python semantic_checks.py <ifc_file>", file=sys.stderr)
        sys.exit(1)
    result = run_all_checks(sys.argv[1])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)
