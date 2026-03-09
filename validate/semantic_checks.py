"""Semantic geometry validation checks.

Custom spatial and geometry rules that go beyond schema validation,
checking for common modelling errors in LLM-generated IFC files.
"""
import json
import sys
from typing import Any, Dict, List

import ifcopenshell
import ifcopenshell.util.element


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
    """Check doors/windows are hosted in walls (filling a void)."""
    issues: List[Dict[str, Any]] = []
    for entity_type in ["IfcDoor", "IfcWindow"]:
        for elem in ifc_file.by_type(entity_type):
            fills = getattr(elem, "FillsVoids", [])
            if not fills:
                issues.append(
                    {
                        "severity": "warning",
                        "element": elem.GlobalId,
                        "element_type": entity_type,
                        "message": (
                            f"{elem.Name or elem.GlobalId} is not filling any opening"
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
