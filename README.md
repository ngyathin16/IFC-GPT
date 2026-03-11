# LLM-IFC-Generation

LLM-driven pipeline to convert natural-language building descriptions into valid **IFC4** files via a Blender 4.4 / Bonsai MCP server.

Forked from [`Show2Instruct/ifc-bonsai-mcp`](https://github.com/Show2Instruct/ifc-bonsai-mcp).

## What Is in This Repo

- **MCP server**
  `src/blender_mcp/` contains the FastMCP server, tool registrations, Blender socket bridge, and RAG support.

- **Blender addon**
  `src/blender_addon/` contains the addon source. A packaged `blender_addon.zip` is already present at the repo root for installation into Blender.

- **LangGraph agent**
  `agent/` contains the LLM-driven pipeline for clarification, plan generation, build orchestration, validation, repair, and export.

- **Validation layer**
  `validate/` contains schema, IDS, and semantic validation scripts. The project IDS file lives at `ids/v0.ids`.

- **Golden tests and fixtures**
  `tests/` includes phase tests and golden IFC generators. Generated fixtures and reports are stored under `tests/output/`.

- **Local workflows and automation**
  `.windsurf/workflows/` contains setup and validation workflows, while `.github/workflows/` contains CI and validation automation.

## Toolchain

- Blender 4.4+
- Bonsai (BlenderBIM) 0.8.2+
- IfcOpenShell + IfcTester
- LangChain / LangGraph
- Python 3.10+
- `uv` for system-side dependency management
- IFC4 only

---

## How to Run

### Prerequisites

| Tool | Purpose |
|---|---|
| [Blender 4.4+](https://www.blender.org/download/) | Runs the addon and provides the live IFC/Bonsai workspace |
| [Bonsai (BlenderBIM)](https://bonsaibim.org/) | IFC authoring and inspection inside Blender |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Installs and runs all system-side Python dependencies |
| Python 3.10+ | Managed by `uv` for the system environment |
| Node.js / `npx` (optional) | Used for MCP Inspector |
| Azure OpenAI or OpenAI-compatible credentials | Required for the agent LLM path |

### Step 1 — Clone and install system dependencies

```bash
git clone <repo-url>
cd IFC-GPT
uv sync --all-extras
```

Create a `.env` file in the repo root. This repo currently does **not** ship a committed `.env.example`, so create it manually.

Preferred Azure configuration used by the current agent:

```env
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://ov-virginia.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-5.1-codex-max
AZURE_OPENAI_API_VERSION=2025-04-01-preview
```

Optional OpenAI-compatible fallback:

```env
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
```

If you only want to run the MCP server or validation scripts, the LLM credentials are not needed until you use the agent.

### Step 2 — Install the Blender addon

1. If you are using the checked-in addon package, use `blender_addon.zip` from the repo root.
2. If you changed files under `src/blender_addon/`, rebuild the zip first:

```bash
uv run python scripts/install.py --create-addon-zip
```

3. Open Blender → **Edit → Preferences → Add-ons → Install from Disk…**
4. Select `blender_addon.zip`.
5. Enable **Blender MCP** in the addon list.
6. Install **Bonsai (BlenderBIM)** separately from [bonsaibim.org](https://bonsaibim.org/).
7. In the 3D View sidebar, look for the `BlenderMCP` tab and connect/start the addon-side bridge.

> The addon runs inside Blender's **embedded Python**. Do not cross-install system packages into Blender or Blender packages into the `uv` environment.

### Step 3 — Start the MCP server

```bash
uv run main.py
```

This uses the repo entry point defined in `main.py`. If you installed the package as a script entry point, `ifc-bonsai-mcp` is also available.

To inspect the server manually:

```bash
npx @modelcontextprotocol/inspector uv --directory . run main.py
```

You should be able to call `ping` and get `pong`.

### Step 4 — Create and open the Blender workspace template

```bash
blender --background --python scripts/create_blend_template.py -- --output workspace/llm_ifc_template.blend
blender workspace/llm_ifc_template.blend
```

The generated template from `create_blend_template.py` provides:

- **3D Viewport**
  IFC model preview via Bonsai.

- **Properties panel**
  IFC element inspection.

- **Text Editor**
  Scratch pad for MCP tool experiments.

- **Info area**
  Operator and event log output.

If Blender is not on your `PATH`, run the same script with the full Blender executable path or open the generated `.blend` file manually.

### Step 5 — Run the agent

With Blender open, Bonsai enabled, and the addon connected, you can drive the repo from the terminal.

Interactive mode:

```bash
uv run scripts/run_agent.py
uv run scripts/run_agent.py --message "I want a 5 storey office building"
```

Non-interactive mode:

```bash
uv run scripts/run_agent.py --message "Create a 6x4m room with one door and two windows" --no-interactive
```

Notes:

- **Agent entrypoint**
  `scripts/run_agent.py` calls `agent.graph.run_pipeline()`.

- **Live vs fallback behavior**
  The pipeline attempts to load the registered MCP tools directly. If live tool loading fails, it falls back to dry-run behavior instead of mutating Blender.

- **Artifacts**
  Execution traces are written to `reports/`. IFC files and viewport captures are typically written under `workspace/`.

### Step 6 — Optional: initialize the local knowledge base and embedding server

If you want the RAG / IFC knowledge search path available locally, initialize the docs index and optionally run the embedding service.

Build or rebuild the ChromaDB index:

```bash
uv run python scripts/init_knowledge_base.py
```

Run the local embedding server:

```bash
uv run python scripts/embedding_server.py --host 127.0.0.1 --port 8080
```

Optional environment variable for remote embeddings:

```env
BLENDER_MCP_REMOTE_EMBEDDINGS_URL=http://127.0.0.1:8080/embeddings
```

### Step 7 — Inspect IDS failures in Bonsai

1. In Blender with Bonsai active, open the generated `.ifc` from `workspace/`, `tests/output/`, or `reports/`.
2. Open the **Bonsai** validation UI.
3. Run IDS validation against `ids/v0.ids`.
4. Inspect failing specifications and highlighted elements in the viewport.

### Step 8 — Run validation independently

Aggregate schema validation:

```bash
uv run python validate/run_validation.py tests/output/golden_simple_room.ifc
```

Individual validation layers:

```bash
uv run python validate/schema_validate.py tests/output/golden_simple_room.ifc
uv run python validate/ids_validate.py tests/output/golden_simple_room.ifc ids/v0.ids
uv run python validate/semantic_checks.py tests/output/golden_simple_room.ifc
```

### Step 9 — Run tests

Full test suite:

```bash
uv run pytest tests/ -v
```

Phase 5 README / distribution checks:

```bash
uv run pytest tests/test_phase5.py -v
```

Golden fixture generators:

```bash
uv run python tests/golden_test_simple_room.py
uv run python tests/golden_test_two_storey.py
```

---

## Environments

| Environment | Purpose |
|---|---|
| System/venv (`uv`) | MCP server, agent, validation scripts, tests, setup utilities |
| Blender embedded Python | Blender addon and Blender-only scripts |

> **Never** mix these two environments. The system-side Python environment and Blender embedded Python are intentionally isolated.

---

## Automation and Workflows

Local workflow documents live in `.windsurf/workflows/`:

- **`/setup-env`**
  End-to-end environment setup.

- **`/full-pipeline`**
  Prompt-to-validated-output walkthrough.

- **`/run-golden-tests`**
  Golden fixtures and validation report workflow.

- **`/validate-ifc`**
  Full validation pipeline for a generated IFC file.

CI automation lives in `.github/workflows/` and currently includes:

- **`ci.yml`**
  Linting, type-checking, tests, golden fixture validation, and Phase 5 checks.

- **`validate-ifc.yml`**
  IFC-focused validation pipeline with artifact upload and Blender integration steps.

---

## Phases

See [`docs/PRODUCT_DEFINITION.md`](docs/PRODUCT_DEFINITION.md) for the acceptance criteria and source-of-truth checklist.

| Phase | Focus | Status |
|---|---|---|
| 1 | MCP Server Foundation | ✅ Done |
| 2 | Component Template Registry | ✅ Done |
| 3 | Validation Layer | 🚧 Implemented, acceptance checklist still being tightened |
| 4 | LangGraph Orchestration | 🚧 Implemented, acceptance checklist still being tightened |
| 5 | UI & Distribution (Blender-first) | ✅ Done |

---

## Repo Layout

```
├── src/blender_mcp/       # MCP server, tool registration, Blender bridge, RAG
├── src/blender_addon/     # Blender addon source packaged as blender_addon.zip
├── agent/                 # LangGraph graph, prompts, schemas, repair logic, LLM client
├── components/            # Primitive registry and template metadata
├── validate/              # Schema, IDS, and semantic validation scripts
├── ids/                   # IDS specifications (including ids/v0.ids)
├── scripts/               # Setup, install, docs generation, agent runner, debug utilities
├── docs/                  # Product definition, API reference, LLM environment notes
├── tests/                 # Phase tests, golden generators, output fixtures
├── .windsurf/workflows/   # Local task workflows for setup and validation
├── .github/workflows/     # CI and IFC validation automation
├── reports/               # Generated reports, screenshots, exported traces
├── workspace/             # Generated .blend, .ifc, and viewport artifacts
└── experiments/           # Scratch and exploratory work
```

## Related Docs

- **Product definition**
  [`docs/PRODUCT_DEFINITION.md`](docs/PRODUCT_DEFINITION.md)

- **API reference**
  [`docs/api-reference.md`](docs/api-reference.md)

- **Troubleshooting**
  [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

- **Contributing**
  [`CONTRIBUTING.md`](CONTRIBUTING.md)
