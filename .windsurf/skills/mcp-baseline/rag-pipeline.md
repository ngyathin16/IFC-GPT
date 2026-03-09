# RAG Pipeline (Appendix B)

## Documents Ingested by the Knowledge Base

The `IFCKnowledgeStore.build_index()` method (in `src/blender_mcp/rag/vector_store.py`) ingests these document sources:

| # | Document | File Path | Type Tag | Size | Generation Script |
|---|----------|-----------|----------|------|-------------------|
| 1 | IfcOpenShell API docs | `docs/ifcopenshell_api_docs.txt` | `function`, `module` | ~441KB | `scripts/generate_ifcopenshell_docs.py` |
| 2 | IFC4x3 Spec (JSONL) | `docs/ifc4x3_spec.jsonl` | `ifc_spec` | ~5-15MB | `scripts/generate_ifc_docs.py` |
| 3 | IFC4x3 Spec (TXT) | `docs/ifc4x3_spec.txt` | `ifc_spec_corpus` | Fallback | Same script |
| 4 | MCP API Reference | `docs/api-reference.md` | `mcp_tools` | ~104KB | `scripts/generate_mcp_docs.py` |
| 5 | LLM Env Helpers | `docs/LLM_ENV.md` | `env_helper` | ~1.6KB | Already in repo |

## Generation Commands (Run in Order)

```bash
# 1. IfcOpenShell API docs — requires ifcopenshell installed
uv run python scripts/generate_ifcopenshell_docs.py

# 2. IFC4x3 spec — web scraper, needs internet, ~2-5 min
#    Scrapes: https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/
uv run python scripts/generate_ifc_docs.py --verbose --max-pages 1500

# 3. MCP API reference — introspects the server's tool definitions
uv run python scripts/generate_mcp_docs.py

# 4. Build vector store — all docs into ChromaDB
uv run python scripts/init_knowledge_base.py --force-rebuild
```

## Additional RAG Documents to Add (Your Enhancements)

For your fork, consider adding these to the `docs/` folder and modifying `vector_store.py`'s `build_index()` to ingest them:

| Document | Source | How to Obtain | Purpose |
|----------|--------|---------------|---------|
| Component Registry | `components/registry.yaml` | You create it (Phase 2) | LLM knows available primitives |
| IDS v0 requirements | `ids/v0.ids` | You create it (Phase 3) | LLM knows validation rules |
| IFC4 Official HTML spec | `https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/` | Download or scrape | Authoritative entity definitions |
| buildingSMART Property Sets | `https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/annex/annex-b.htm` | Download | Standard property sets reference |
| Golden test examples | `tests/golden_test_*.py` | You create them | Few-shot examples for the LLM |
| Hong Kong Building Regulations | BD internal docs | Internal procurement | Code compliance (v1+) |

## How the RAG Parser Works

The `IFCDocumentParser` (in `src/blender_mcp/rag/document_parser.py`) parses `ifcopenshell_api_docs.txt` using regex patterns:

- **Module pattern:** `## Module: <name>` → extracts description and function list
- **Function pattern:** `#### <func_name>` → extracts signature, docstring, parameters, examples
- Each function becomes a `Document` with metadata: `{module, function, type: "function", full_path, full_doc}`
- Each module becomes a `Document` with metadata: `{module, type: "module", function_count}`

The IFC spec docs (JSONL) are ingested as-is: each line becomes a `Document` with `{type: "ifc_spec", url, title}`.

## Vector Store Configuration

- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, fast, good for code/docs)
- **Vector store:** ChromaDB (persisted to `.cache/chromadb/`)
- **Collection name:** `ifc_knowledge`
- **Text splitter:** LangChain `RecursiveCharacterTextSplitter` (applied to large docs)

## Extending the RAG for Your Fork

To add your own documents to the knowledge base, modify `src/blender_mcp/rag/vector_store.py`'s `build_index()` method. Add after the existing doc loading:

```python
# In build_index(), after existing document loading:

# Load component registry
registry_path = project_root / "components" / "registry.yaml"
if registry_path.exists():
    import yaml
    content = registry_path.read_text(encoding="utf-8")
    documents.append(Document(
        page_content=content,
        metadata={"type": "component_registry", "module": "components", "source": str(registry_path)}
    ))

# Load IDS requirements
ids_dir = project_root / "ids"
if ids_dir.exists():
    for ids_file in ids_dir.glob("*.ids"):
        content = ids_file.read_text(encoding="utf-8")
        documents.append(Document(
            page_content=content,
            metadata={"type": "ids_requirements", "module": "validation", "source": str(ids_file)}
        ))

# Load golden test examples
tests_dir = project_root / "tests"
if tests_dir.exists():
    for test_file in tests_dir.glob("golden_test_*.py"):
        content = test_file.read_text(encoding="utf-8")
        documents.append(Document(
            page_content=content,
            metadata={"type": "golden_example", "module": "examples", "source": str(test_file)}
        ))
```
