"""CI helper: Check validation JSON reports and fail if errors found."""
import json
import sys
from pathlib import Path


def check_report(path: str) -> bool:
    """Return True if the report indicates a valid result."""
    with open(path) as f:
        report = json.load(f)

    valid = report.get("valid", True)
    errors = report.get("error_count", 0)

    status = "PASS" if valid else "FAIL"
    print(f"  {Path(path).name}: {status} ({errors} errors)")
    return bool(valid)


if __name__ == "__main__":
    all_pass = True
    for report_file in sys.argv[1:]:
        if not Path(report_file).exists():
            print(f"  SKIP {report_file} (not found)")
            continue
        if not check_report(report_file):
            all_pass = False

    sys.exit(0 if all_pass else 1)
