---
name: ifc-project-master
description: >
  Master project rules for the LLM→IFC generation pipeline. Covers architecture
  overview, code style, environment constraints, and IFC domain knowledge.
  Activate for any IFC-related development task.
---

## Architecture
User prompt → LangGraph agent → MCP server (stdio) → Blender 4.4+/Bonsai → output.ifc
→ Validation (schema+IDS+semantic) → Repair loop (max 3×) → Export (.ifc + report)

## Critical Constraints
- TWO Python environments: system venv (MCP server) ≠ Blender embedded Python. NEVER confuse them.
- ALL IFC operations via `ifcopenshell.api.run()` — no raw entity manipulation.
- ALWAYS call `save_and_load_ifc()` after IFC mutations.
- Use `logging`, NEVER `print()` — breaks MCP stdio transport.
- Coordinates in meters, Z-up. IFC4 schema only.
- v0 scope: architectural shell only (walls, slabs, doors, windows, roofs, stairs). No MEP.

## Code Style
- Python 3.10+, type hints everywhere.
- Module docstrings on every file.
- Docstrings with Args/Returns/Raises.
- Use `uv` for dependency management.
- JSON-serializable inputs/outputs for MCP tools.
- Tests in `tests/`, validation in `validate/`, agent in `agent/`.

## IFC Domain Quick Reference
- Spatial hierarchy: IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey → elements
- Wall axis: center line from start→end; thickness extends both sides
- Openings: use `distance_along_wall` (wall-relative), not global coords
- Registry: `components/registry.yaml` defines ALL allowed building primitives
- IDS: `ids/v0.ids` defines 13 validation specifications

## Directory Layout (canonical)
- `src/blender_mcp/` — MCP server (forked from ifc-bonsai-mcp)
- `components/` — Template registry + primitives
- `validate/` — Validation scripts (schema, IDS, semantic)
- `ids/` — IDS XML files
- `agent/` — LangGraph orchestration
- `docs/` — RAG source docs + product definition
- `scripts/` — Utility scripts (each must have --help)
- `tests/` — pytest tests + golden IFC fixtures in tests/output/
- `reports/` — Validation report output (git-ignored build artifacts)
