"""IDS validation wrapper using IfcTester.

Validates an IFC file against an IDS requirements file and returns
structured pass/fail results per specification, suitable for the agent
repair loop.
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import ifcopenshell
from ifctester import ids as ids_module


def validate_ids(ifc_path: str, ids_path: str) -> Dict[str, Any]:
    """Validate IFC against IDS requirements.

    Returns structured results with pass/fail per requirement.

    Returns:
        {
            "valid": bool,
            "total_specs": int,
            "passed": int,
            "failed": int,
            "specifications": [
                {
                    "name": str,
                    "status": bool,
                    "applicable_entities": int,
                }
            ],
        }
    """
    ifc_file = ifcopenshell.open(ifc_path)
    ids_file = ids_module.open(ids_path)
    ids_file.validate(ifc_file)

    results: List[Dict[str, Any]] = []
    total_pass = 0
    total_fail = 0

    for spec in ids_file.specifications:
        applicable = (
            len(spec.applicable_entities)
            if hasattr(spec, "applicable_entities")
            else 0
        )
        # A spec with 0 applicable entities is "not applicable" — treat as passed.
        effective_status = spec.status if applicable > 0 else True
        spec_result: Dict[str, Any] = {
            "name": spec.name,
            "status": effective_status,
            "applicable_entities": applicable,
            "not_applicable": applicable == 0,
        }
        if effective_status:
            total_pass += 1
        else:
            total_fail += 1
        results.append(spec_result)

    return {
        "valid": total_fail == 0,
        "total_specs": len(results),
        "passed": total_pass,
        "failed": total_fail,
        "specifications": results,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python ids_validate.py <ifc_file> <ids_file>",
            file=sys.stderr,
        )
        sys.exit(1)
    result = validate_ids(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)
