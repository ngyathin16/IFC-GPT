---
description: Run all golden tests and report validation results
---

# Golden Test Runner

## Step 1: Run Phase 2 Golden Tests
Run `uv run pytest tests/golden_test_simple_room.py tests/golden_test_two_storey.py -v` and capture output.

## Step 2: Collect Validation Results
Read `tests/output/golden_simple_room_validation.json` and `tests/output/golden_two_storey_validation.json`.

## Step 3: Run Phase 3 Validation Tests (if present)
Run `uv run pytest tests/test_phase3.py -v` if the file exists.

## Step 4: Report
Summarize results in a table:

| Test | Schema | IDS | Semantic | Overall |
|------|--------|-----|----------|---------|
| golden_simple_room | PASS/FAIL | X/13 | PASS/FAIL | ✅/❌ |
| golden_two_storey  | PASS/FAIL | X/13 | PASS/FAIL | ✅/❌ |

- If any failures: show the specific errors and suggest targeted fixes.
- If all pass: confirm the test suite is green and the phase is ready for handoff.
