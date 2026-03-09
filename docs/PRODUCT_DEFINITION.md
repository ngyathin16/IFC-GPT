# Product Definition — LLM-IFC-Generation

## Vision
An LLM-driven pipeline that converts natural-language building descriptions into valid IFC4 files via a Blender/Bonsai MCP server, enabling non-expert users to author BIM models through conversation.

## Upstream Fork
`Show2Instruct/ifc-bonsai-mcp` — provides the MCP server skeleton and Blender addon bridge.

## Toolchain
| Component | Version |
|---|---|
| Blender | 4.4+ |
| Bonsai (BlenderBIM) | 0.8.2+ |
| IfcOpenShell | latest stable |
| LangGraph | 0.1+ |
| Python | 3.10+ |
| IFC schema | IFC4 |

---

## Phases & Acceptance Criteria

### Phase 1 — MCP Server Foundation
- [x] Fork cloned locally; `uv` environment boots with no errors.
- [x] MCP server starts and responds to a `ping` tool call from a test client.
- [x] Blender addon loads in Blender 4.4 without console errors.
- [x] Module docstrings present on every `.py` file.

### Phase 2 — Component Template Registry
- [x] At least 5 parametric IFC4 component templates stored under `components/`.
- [x] Each template can be instantiated via a single MCP tool call.
- [x] Unit tests in `tests/` pass for all templates.

### Phase 3 — Validation Layer
- [ ] `validate/` scripts run `ifcopenshell.validate` against any generated `.ifc` file.
- [ ] IDS rules in `ids/` enforce project-specific constraints (e.g., required property sets).
- [ ] CI pipeline runs validation on every PR and fails on schema errors.

### Phase 4 — LangGraph Orchestration
- [ ] `agent/` contains a LangGraph graph that: (a) parses user intent, (b) selects templates, (c) calls MCP tools, (d) validates output.
- [ ] End-to-end golden test: prompt → valid `.ifc` file round-trip passes in `tests/`.
- [ ] Validation report written to `reports/` on each run.

---

## Non-Functional Requirements
- All IFC operations via `ifcopenshell.api` only — no raw entity manipulation.
- Two isolated Python environments: system/venv (MCP server) and Blender embedded Python. Scripts must explicitly target the correct one.
- `uv` manages all system-side dependencies; `pyproject.toml` is the single source of truth.
- No secrets committed; use `.env` + `python-dotenv` for API keys.

## Out of Scope (v1)
- IFC2x3 support.
- Real-time multi-user collaboration.
- Production deployment / cloud hosting.
