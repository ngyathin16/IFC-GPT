"""Validation script: runs ifcopenshell.validate against one or more IFC files."""

import argparse
import logging
import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.validate


def validate_file(ifc_path: Path, logger: logging.Logger) -> bool:
    """Validate a single IFC file. Returns True if valid, False otherwise."""
    logger.info("Validating %s", ifc_path)
    model = ifcopenshell.open(str(ifc_path))
    json_logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, json_logger)
    issues = json_logger.statements
    if issues:
        for issue in issues:
            logger.error("  %s", issue)
        return False
    logger.info("  OK — no issues found.")
    return True


def main() -> None:
    """Entry point for IFC validation CLI."""
    parser = argparse.ArgumentParser(
        description="Validate IFC4 files using ifcopenshell.validate."
    )
    parser.add_argument(
        "ifc_files",
        nargs="+",
        type=Path,
        metavar="FILE",
        help="One or more .ifc files to validate.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger(__name__)

    failed: list[Path] = []
    for ifc_path in args.ifc_files:
        if not ifc_path.exists():
            logger.error("File not found: %s", ifc_path)
            failed.append(ifc_path)
            continue
        if not validate_file(ifc_path, logger):
            failed.append(ifc_path)

    if failed:
        logger.error("%d file(s) failed validation: %s", len(failed), failed)
        sys.exit(1)

    logger.info("All %d file(s) passed validation.", len(args.ifc_files))


if __name__ == "__main__":
    main()
