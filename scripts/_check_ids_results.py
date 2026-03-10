"""Print IDS validation results from a JSON report."""
import json
import sys
from pathlib import Path

path = sys.argv[1] if len(sys.argv) > 1 else "tests/output/golden_ten_storey_validation.json"
r = json.load(open(path, encoding="utf-8"))

ids = r.get("ids", {})
print(f"IDS valid: {ids.get('valid')}  passed={ids.get('passed')}  failed={ids.get('failed')}")
print()
for s in ids.get("specifications", []):
    status = "PASS" if s["status"] else "FAIL"
    na = " [N/A]" if s.get("not_applicable") else ""
    print(f"  [{status}]{na} {s['name']}  ({s['applicable_entities']} entities)")

print()
print("Semantic issues:")
for issue in r.get("semantic", {}).get("issues", []):
    print(f"  [{issue['severity'].upper()}] {issue['element_type']} {issue['element']}: {issue['message']}")
