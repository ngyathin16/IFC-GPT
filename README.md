# LLM-IFC-Generation

LLM-driven pipeline to convert natural-language building descriptions into valid **IFC4** files via a Blender 4.4 / Bonsai MCP server.

Forked from [`Show2Instruct/ifc-bonsai-mcp`](https://github.com/Show2Instruct/ifc-bonsai-mcp).

## Toolchain
- Blender 4.4+ / Bonsai 0.8.2+
- IfcOpenShell (latest stable)
- LangGraph 0.1+
- Python 3.10+

## Quick Start

```bash
# 1. Install uv
pip install uv

# 2. Create environment and install dependencies
uv sync --all-extras

# 3. Copy env template
cp .env.example .env   # then fill in API keys

# 4. Run tests
uv run pytest
```

## Environments
| Environment | Purpose |
|---|---|
| System/venv (`uv`) | MCP server, agent, validation scripts |
| Blender embedded Python | Blender addon only — managed separately |

> **Never** mix these two environments. See `.windsurf/rules/python.md`.

## Phases
See [`docs/PRODUCT_DEFINITION.md`](docs/PRODUCT_DEFINITION.md) for full acceptance criteria per phase.

| Phase | Focus |
|---|---|
| 1 | MCP Server Foundation |
| 2 | Component Template Registry |
| 3 | Validation Layer |
| 4 | LangGraph Orchestration |

## Repo Layout
```
├── src/blender_mcp/     # MCP server (forked)
│   ├── mcp_functions/   # Tool definitions
│   └── rag/             # RAG knowledge base
├── components/          # Template registry (Phase 2)
├── validate/            # Validation scripts (Phase 3)
├── ids/                 # IDS files (Phase 3)
├── agent/               # LangGraph orchestration (Phase 4)
├── docs/                # RAG source docs + product definition
├── scripts/             # Utility scripts
├── tests/               # pytest golden tests
└── reports/             # Validation reports output
```
