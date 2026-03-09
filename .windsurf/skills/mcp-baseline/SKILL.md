---
name: mcp-baseline
description: Setting up and running the IFC-Bonsai MCP server baseline, including Blender addon installation, RAG knowledge base initialization, and basic tool testing.
---

## MCP Server Architecture
The server runs as a stdio MCP server in a system venv. Blender runs separately with its own Python.
Communication: MCP server ↔ Blender addon via localhost socket.

## Key Files
- `src/blender_mcp/server.py` — MCP server entry point
- `src/blender_mcp/mcp_functions/api_tools.py` — 42 IFC creation/query tools (136KB)
- `src/blender_mcp/mcp_functions/rag_tools.py` — 8 RAG knowledge tools
- `src/blender_mcp/mcp_functions/analysis_tools.py` — 2 screenshot tools
- `src/blender_mcp/rag/vector_store.py` — ChromaDB vector store (IFCKnowledgeStore)
- `src/blender_mcp/rag/document_parser.py` — IfcOpenShell doc parser
- `scripts/init_knowledge_base.py` — KB initialization

## RAG Document Pipeline
1. `scripts/generate_ifcopenshell_docs.py` → `docs/ifcopenshell_api_docs.txt`
2. `scripts/generate_ifc_docs.py` → `docs/ifc4x3_spec.jsonl`
3. `scripts/generate_mcp_docs.py` → `docs/api-reference.md`
4. `scripts/init_knowledge_base.py` → `.cache/chromadb/`

## Environment Variables
- `BLENDER_MCP_EMBEDDING_MODEL` — Override embedding model (default: sentence-transformers/all-MiniLM-L6-v2)
- `BLENDER_MCP_EMBEDDING_CACHE` — Local model cache directory
- `BLENDER_MCP_REMOTE_EMBEDDINGS_URL` — Remote embedding service URL
- `BLENDER_MCP_EMBEDDING_OFFLINE` — Set to "1" for offline mode

## Common Pitfalls
- Blender Python ≠ system Python. `ifcopenshell` must be installed in BOTH.
- The embedding server must be running before RAG queries work.
- `save_and_load_ifc()` must be called after IFC mutations to update Blender viewport.
