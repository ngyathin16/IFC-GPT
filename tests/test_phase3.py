"""Phase 3 acceptance tests — Validation Pipeline.

Verifies exit criteria for Steps 3.1, 3.2, and 3.3:
  - validate_schema() returns structured JSON with required keys
  - validate_schema() returns valid=True for golden IFC fixtures
  - validate_ids() returns structured JSON with required keys
  - validate_ids() returns valid=True for golden IFC fixtures
  - run_all_checks() returns structured JSON with required keys
  - run_all_checks() returns valid=True (zero errors) for golden IFC fixtures
  - All validate/*.py modules have module-level docstrings
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATE_DIR = PROJECT_ROOT / "validate"
IDS_PATH = PROJECT_ROOT / "ids" / "v0.ids"
GOLDEN_SIMPLE = PROJECT_ROOT / "tests" / "output" / "golden_simple_room.ifc"
GOLDEN_TWO_STOREY = PROJECT_ROOT / "tests" / "output" / "golden_two_storey.ifc"

GOLDEN_FILES = [
    pytest.param(str(GOLDEN_SIMPLE), id="golden_simple_room"),
    pytest.param(str(GOLDEN_TWO_STOREY), id="golden_two_storey"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_golden_exists(path: str) -> None:
    """Regenerate golden IFC if missing by running the golden test script."""
    p = Path(path)
    if not p.exists():
        script = PROJECT_ROOT / "tests" / f"golden_test_{p.stem}.py"
        if script.exists():
            subprocess.run(
                [sys.executable, str(script)],
                check=True,
                cwd=str(PROJECT_ROOT),
            )


# ---------------------------------------------------------------------------
# Step 3.1: Schema Validation
# ---------------------------------------------------------------------------


class TestSchemaValidate:
    def test_importable(self) -> None:
        """validate.schema_validate must be importable."""
        from validate.schema_validate import validate_schema  # type: ignore[import]  # noqa: F401

    def test_returns_required_keys(self) -> None:
        """validate_schema() must return a dict with all required keys."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        from validate.schema_validate import validate_schema  # type: ignore[import]

        result = validate_schema(str(GOLDEN_SIMPLE))
        required = {"valid", "schema", "errors", "warnings", "error_count", "warning_count"}
        assert required.issubset(result.keys()), (
            f"Missing keys: {required - result.keys()}"
        )

    def test_valid_key_is_bool(self) -> None:
        """validate_schema() 'valid' field must be a bool."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        from validate.schema_validate import validate_schema  # type: ignore[import]

        result = validate_schema(str(GOLDEN_SIMPLE))
        assert isinstance(result["valid"], bool)

    @pytest.mark.parametrize("ifc_path", GOLDEN_FILES)
    def test_golden_passes_schema(self, ifc_path: str) -> None:
        """Golden IFC fixtures must pass schema validation (zero errors)."""
        _ensure_golden_exists(ifc_path)
        from validate.schema_validate import validate_schema  # type: ignore[import]

        result = validate_schema(ifc_path)
        assert result["valid"] is True, (
            f"Schema errors in {ifc_path}: {result['errors']}"
        )
        assert result["error_count"] == 0

    def test_schema_field_is_string(self) -> None:
        """validate_schema() 'schema' field must be a non-empty string."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        from validate.schema_validate import validate_schema  # type: ignore[import]

        result = validate_schema(str(GOLDEN_SIMPLE))
        assert isinstance(result["schema"], str) and result["schema"]

    def test_cli_exits_zero_for_valid_ifc(self) -> None:
        """CLI must exit 0 for a valid IFC file."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        proc = subprocess.run(
            [sys.executable, str(VALIDATE_DIR / "schema_validate.py"), str(GOLDEN_SIMPLE)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"

    def test_cli_outputs_valid_json(self) -> None:
        """CLI stdout must be valid JSON."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        proc = subprocess.run(
            [sys.executable, str(VALIDATE_DIR / "schema_validate.py"), str(GOLDEN_SIMPLE)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        parsed = json.loads(proc.stdout)
        assert "valid" in parsed


# ---------------------------------------------------------------------------
# Step 3.2: IDS Validation
# ---------------------------------------------------------------------------


class TestIdsFile:
    def test_ids_file_exists(self) -> None:
        """ids/v0.ids must exist."""
        assert IDS_PATH.exists(), f"Missing IDS file: {IDS_PATH}"

    def test_ids_file_is_valid_xml(self) -> None:
        """ids/v0.ids must be parseable as XML."""
        import xml.etree.ElementTree as ET

        ET.parse(str(IDS_PATH))

    def test_ids_has_13_specifications(self) -> None:
        """ids/v0.ids must contain exactly 13 specifications."""
        import xml.etree.ElementTree as ET

        tree = ET.parse(str(IDS_PATH))
        ns = {"ids": "http://standards.buildingsmart.org/IDS"}
        specs = tree.findall(".//ids:specification", ns)
        assert len(specs) == 13, f"Expected 13 specifications, found {len(specs)}"


class TestIdsValidate:
    def test_importable(self) -> None:
        """validate.ids_validate must be importable."""
        from validate.ids_validate import validate_ids  # type: ignore[import]  # noqa: F401

    def test_returns_required_keys(self) -> None:
        """validate_ids() must return a dict with all required keys."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        from validate.ids_validate import validate_ids  # type: ignore[import]

        result = validate_ids(str(GOLDEN_SIMPLE), str(IDS_PATH))
        required = {"valid", "total_specs", "passed", "failed", "specifications"}
        assert required.issubset(result.keys()), (
            f"Missing keys: {required - result.keys()}"
        )

    def test_specifications_is_list(self) -> None:
        """validate_ids() 'specifications' must be a list."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        from validate.ids_validate import validate_ids  # type: ignore[import]

        result = validate_ids(str(GOLDEN_SIMPLE), str(IDS_PATH))
        assert isinstance(result["specifications"], list)

    def test_spec_count_matches_ids_file(self) -> None:
        """total_specs must equal the number of specifications in v0.ids."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        from validate.ids_validate import validate_ids  # type: ignore[import]

        result = validate_ids(str(GOLDEN_SIMPLE), str(IDS_PATH))
        assert result["total_specs"] == 13, (
            f"Expected 13 specs, got {result['total_specs']}"
        )

    @pytest.mark.parametrize("ifc_path", GOLDEN_FILES)
    def test_golden_passes_ids(self, ifc_path: str) -> None:
        """Golden IFC fixtures must pass all IDS specifications."""
        _ensure_golden_exists(ifc_path)
        from validate.ids_validate import validate_ids  # type: ignore[import]

        result = validate_ids(ifc_path, str(IDS_PATH))
        failed = [s for s in result["specifications"] if not s["status"]]
        assert result["valid"] is True, (
            f"IDS failures in {ifc_path}: {[s['name'] for s in failed]}"
        )

    def test_cli_exits_zero_for_valid_ifc(self) -> None:
        """CLI must exit 0 for a valid IFC + IDS combination."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        proc = subprocess.run(
            [
                sys.executable,
                str(VALIDATE_DIR / "ids_validate.py"),
                str(GOLDEN_SIMPLE),
                str(IDS_PATH),
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"

    def test_cli_outputs_valid_json(self) -> None:
        """CLI stdout must be valid JSON."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        proc = subprocess.run(
            [
                sys.executable,
                str(VALIDATE_DIR / "ids_validate.py"),
                str(GOLDEN_SIMPLE),
                str(IDS_PATH),
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        parsed = json.loads(proc.stdout)
        assert "valid" in parsed


# ---------------------------------------------------------------------------
# Step 3.3: Semantic Checks
# ---------------------------------------------------------------------------


class TestSemanticChecks:
    def test_importable(self) -> None:
        """validate.semantic_checks must be importable."""
        from validate.semantic_checks import run_all_checks  # type: ignore[import]  # noqa: F401

    def test_returns_required_keys(self) -> None:
        """run_all_checks() must return a dict with all required keys."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        from validate.semantic_checks import run_all_checks  # type: ignore[import]

        result = run_all_checks(str(GOLDEN_SIMPLE))
        required = {"valid", "error_count", "warning_count", "issues"}
        assert required.issubset(result.keys()), (
            f"Missing keys: {required - result.keys()}"
        )

    def test_issues_is_list(self) -> None:
        """run_all_checks() 'issues' must be a list."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        from validate.semantic_checks import run_all_checks  # type: ignore[import]

        result = run_all_checks(str(GOLDEN_SIMPLE))
        assert isinstance(result["issues"], list)

    @pytest.mark.parametrize("ifc_path", GOLDEN_FILES)
    def test_golden_passes_semantic(self, ifc_path: str) -> None:
        """Golden IFC fixtures must pass semantic checks (zero errors)."""
        _ensure_golden_exists(ifc_path)
        from validate.semantic_checks import run_all_checks  # type: ignore[import]

        result = run_all_checks(ifc_path)
        errors = [i for i in result["issues"] if i["severity"] == "error"]
        assert result["valid"] is True, (
            f"Semantic errors in {ifc_path}: {errors}"
        )
        assert result["error_count"] == 0

    def test_individual_check_functions_importable(self) -> None:
        """Individual check functions must be importable."""
        from validate.semantic_checks import (  # type: ignore[import]  # noqa: F401
            check_floating_openings,
            check_spatial_containment,
            check_zero_thickness_slabs,
            check_disconnected_storeys,
        )

    def test_cli_exits_zero_for_valid_ifc(self) -> None:
        """CLI must exit 0 for a semantically valid IFC file."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        proc = subprocess.run(
            [sys.executable, str(VALIDATE_DIR / "semantic_checks.py"), str(GOLDEN_SIMPLE)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"

    def test_cli_outputs_valid_json(self) -> None:
        """CLI stdout must be valid JSON."""
        _ensure_golden_exists(str(GOLDEN_SIMPLE))
        proc = subprocess.run(
            [sys.executable, str(VALIDATE_DIR / "semantic_checks.py"), str(GOLDEN_SIMPLE)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        parsed = json.loads(proc.stdout)
        assert "valid" in parsed


# ---------------------------------------------------------------------------
# Module docstrings (validate/*.py)
# ---------------------------------------------------------------------------


class TestValidateModuleDocstrings:
    @pytest.mark.parametrize(
        "py_file",
        list(VALIDATE_DIR.glob("*.py")),
        ids=lambda p: p.name,
    )
    def test_has_module_docstring(self, py_file: Path) -> None:
        """Every .py file in validate/ must have a module-level docstring."""
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            pytest.fail(f"SyntaxError in {py_file.name}: {exc}")
        docstring = ast.get_docstring(tree)
        assert docstring, f"Missing module docstring in validate/{py_file.name}"
