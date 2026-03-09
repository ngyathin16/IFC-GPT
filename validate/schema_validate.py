"""IFC schema validation wrapper.

Runs ifcopenshell.validate against a generated IFC file and returns
structured error/warning results suitable for the agent repair loop.
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import ifcopenshell
import ifcopenshell.validate


def validate_schema(ifc_path: str) -> Dict[str, Any]:
    """Validate IFC file against its declared schema.

    Returns:
        {
            "valid": bool,
            "schema": str,          # e.g. "IFC4"
            "errors": [...],        # List of error dicts
            "warnings": [...],      # List of warning dicts
            "error_count": int,
            "warning_count": int,
        }
    """
    ifc_file = ifcopenshell.open(ifc_path)
    schema = ifc_file.schema

    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(ifc_file, logger)

    errors: List[Dict[str, Any]] = [
        e for e in logger.statements if e.get("severity") == "Error"
    ]
    warnings: List[Dict[str, Any]] = [
        w for w in logger.statements if w.get("severity") == "Warning"
    ]

    return {
        "valid": len(errors) == 0,
        "schema": schema,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python schema_validate.py <ifc_file>", file=sys.stderr)
        sys.exit(1)
    result = validate_schema(sys.argv[1])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)
