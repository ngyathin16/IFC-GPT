---
trigger: always_on
---

## Repository Rules

- Directory layout must match `docs/PRODUCT_DEFINITION.md`. Do not add top-level directories without updating that document.
- All reports (validation, test results) are written to `reports/`. This directory is git-ignored for build artifacts but tracked for golden baselines.
- `tests/` contains pytest tests only. Golden `.ifc` files used as fixtures live in `tests/fixtures/`.
- `scripts/` contains one-off utility scripts. Each script must have a `--help` flag via `argparse` or `click`.
- Commit messages follow Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`.
- Branch naming: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`.
