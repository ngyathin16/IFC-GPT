# LLM-IFC-Generation

LLM-driven pipeline to convert natural-language building descriptions into valid **IFC4** files via a Blender 4.4 / Bonsai MCP server.

Forked from [`Show2Instruct/ifc-bonsai-mcp`](https://github.com/Show2Instruct/ifc-bonsai-mcp).

## Toolchain
- Blender 4.4+ / Bonsai (BlenderBIM) 0.8.2+
- IfcOpenShell (latest stable)
- LangGraph 0.1+
- Python 3.10+

---

## How to Run

### Prerequisites

| Tool | Install |
|---|---|
| [Blender 4.4+](https://www.blender.org/download/) | Download from blender.org |
| [Bonsai (BlenderBIM)](https://bonsaibim.org/) | Install as a Blender addon (see below) |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | `pip install uv` or installer script |
| Python 3.10+ | Managed by uv |

### Step 1 — Clone & install system dependencies

```bash
git clone <repo-url>
cd IFC-GPT

# Install all Python dependencies into a uv-managed venv
uv sync --all-extras

# Copy the env template and fill in your API keys
cp .env.example .env
```

Required `.env` keys:

```
OPENAI_API_KEY=sk-...          # LLM calls in the agent
```

### Step 2 — Install Blender addon

1. Open Blender → **Edit → Preferences → Add-ons → Install from Disk…**
2. Select `blender_addon.zip` from the repo root.
3. Enable **"IFC Bonsai MCP"** in the addon list.
4. Also install **Bonsai (BlenderBIM)** addon from [bonsaibim.org](https://bonsaibim.org/) — required for IFC viewing.

> The Blender addon runs inside Blender's **embedded Python** — never install packages there with pip. It is managed separately from the uv environment.

### Step 3 — Start the MCP server

```bash
# From the repo root, in your uv environment:
uv run main.py
```

The server listens on stdio by default. Verify it's running:

```bash
npx @modelcontextprotocol/inspector uv --directory . run main.py
```

You should see a `ping → pong` response in the inspector.

### Step 4 — Open the Blender workspace template

```bash
# Generate the pre-configured .blend template (requires Blender on PATH):
blender --background --python scripts/create_blend_template.py -- --output workspace/llm_ifc_template.blend

# Then open it:
blender workspace/llm_ifc_template.blend
```

The template provides:
- **3D Viewport** — IFC model preview via Bonsai
- **Properties panel** — IFC element inspector
- **Text Editor** — scratch pad for MCP tool calls
- **Info log** — MCP server event stream

If Blender is not on your PATH, open the `.blend` file directly from File → Open after generating it.

### Step 5 — Generate an IFC model

With the MCP server running and Blender open:

1. In Blender's **Text Editor**, call MCP tools directly, or
2. Use the **agent pipeline** from the terminal:

```bash
uv run python -c "
from agent.graph import app
from langchain_core.messages import HumanMessage

result = app.invoke({
    'messages': [HumanMessage(content='Create a simple 6x4m room with one door and two windows')],
    'building_plan': {},
    'tool_calls_log': [],
    'validation_results': {},
    'repair_attempts': 0,
    'final_ifc_path': '',
    'ids_report_path': 'ids/v0.ids',
    'scene_overview': '',
})
print('Done. Report written to reports/')
"
```

### Step 6 — Inspect IDS failures in Bonsai

1. In Blender with Bonsai active: **File → Open IFC** → select the generated `.ifc` from `tests/output/` or `reports/`.
2. Open the **Bonsai panel** (N-panel) → **Validation** tab.
3. Run **IDS Validation** pointing to `ids/v0.ids` to see pass/fail per specification.
4. Elements with failures are highlighted in the 3D viewport.

### Step 7 — Run validation independently

```bash
# Schema validation
uv run python validate/schema_validate.py tests/output/golden_simple_room.ifc

# IDS validation
uv run python validate/ids_validate.py tests/output/golden_simple_room.ifc ids/v0.ids

# Semantic checks
uv run python validate/semantic_checks.py tests/output/golden_simple_room.ifc
```

### Step 8 — Run all tests

```bash
uv run pytest tests/ -v
```

---

## Environments

| Environment | Purpose |
|---|---|
| System/venv (`uv`) | MCP server, agent, validation scripts |
| Blender embedded Python | Blender addon only — managed separately |

> **Never** mix these two environments. See `.windsurf/rules/python.md`.

---

## Phases

See [`docs/PRODUCT_DEFINITION.md`](docs/PRODUCT_DEFINITION.md) for full acceptance criteria per phase.

| Phase | Focus | Status |
|---|---|---|
| 1 | MCP Server Foundation | ✅ Done |
| 2 | Component Template Registry | ✅ Done |
| 3 | Validation Layer | ✅ Done |
| 4 | LangGraph Orchestration | ✅ Done |
| 5 | UI & Distribution (Blender-first) | ✅ Done |

---

## Repo Layout

```
├── src/blender_mcp/     # MCP server (forked)
│   ├── mcp_functions/   # Tool definitions
│   └── rag/             # RAG knowledge base
├── components/          # Template registry (Phase 2)
├── validate/            # Validation scripts (Phase 3)
├── ids/                 # IDS files (Phase 3)
├── agent/               # LangGraph orchestration (Phase 4)
├── scripts/             # Utility scripts (incl. create_blend_template.py)
├── docs/                # RAG source docs + product definition
├── tests/               # pytest golden tests
├── reports/             # Validation reports output
└── workspace/           # Generated Blender workspace files (git-ignored)
```
