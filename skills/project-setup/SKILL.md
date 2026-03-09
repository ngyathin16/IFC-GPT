---
name: project-setup
description: Initial project scaffolding for the LLM-IFC-Generation fork. Use when setting up repo structure, CI, or dev environment.
---

## Project Context
We are forking https://github.com/Show2Instruct/ifc-bonsai-mcp to build an LLM→IFC generation pipeline.
Target: IFC4 schema. Toolchain: Blender 4.4+ / Bonsai 0.8.2+ / IfcOpenShell / LangGraph.

## Repo Structure Convention
```
project-root/
├── .windsurf/skills/          # IDE skill files
├── src/blender_mcp/           # MCP server (forked)
│   ├── mcp_functions/         # Tool definitions
│   └── rag/                   # RAG knowledge base
├── components/                # Template registry (Phase 2)
├── validate/                  # Validation scripts (Phase 3)
├── ids/                       # IDS files (Phase 3)
├── agent/                     # LangGraph orchestration (Phase 4)
├── docs/                      # RAG source docs
├── scripts/                   # Utility scripts
├── tests/                     # Golden tests
└── reports/                   # Validation reports output
```

## Rules
- Python 3.10+ with type hints everywhere.
- Use `uv` for dependency management, not pip directly.
- Two Python environments: system/venv (MCP server) and Blender's embedded Python (addon). NEVER confuse them.
- All IFC operations use `ifcopenshell.api` — never raw entity manipulation unless absolutely necessary.
- Every file must have a module docstring.