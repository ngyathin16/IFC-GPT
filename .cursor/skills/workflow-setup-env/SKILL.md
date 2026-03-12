---
name: workflow-setup-env
description: Set up the complete development environment from scratch. Use when onboarding to the project or rebuilding the environment after a clean checkout.
---

## Step 1: Install Python Dependencies
Run `uv sync` to install all system-side dependencies from `pyproject.toml`.

## Step 2: Install Blender Packages
Run `python scripts/install_blender_packages.py` to install required packages into Blender's embedded Python.

## Step 3: Generate IfcOpenShell API Docs
Run `uv run python scripts/generate_ifcopenshell_docs.py` to produce `docs/ifcopenshell_api_docs.txt`.

## Step 4: Generate IFC4x3 Spec Docs
Run `uv run python scripts/generate_ifc_docs.py --verbose --max-pages 1500` to scrape and produce `docs/ifc4x3_spec.jsonl`. This requires internet access and takes 2–5 minutes.

## Step 5: Generate MCP API Reference
Run `uv run python scripts/generate_mcp_docs.py` to produce `docs/api-reference.md` from introspecting the MCP server tool definitions.

## Step 6: Build Vector Store
Run `uv run python scripts/init_knowledge_base.py` to ingest all docs into ChromaDB at `.cache/chromadb/`.

## Step 7: Start Blender
Open Blender 4.4+ with the Bonsai addon enabled. Verify the addon loads without console errors.

## Step 8: Start Embedding Server
Run `uv run python scripts/embedding_server.py --host 127.0.0.1 --port 8080` in a separate terminal (non-blocking).

## Step 9: Verify MCP Connection
Call `get_ifc_scene_overview` from the MCP client. Confirm it returns valid project info.

## Step 10: Verify RAG
Call `search_ifc_knowledge` with query `"create wall"`. Confirm results are returned with function signatures.

## Step 11: Report
- List which steps passed and which failed.
- For any failure, diagnose the root cause and suggest a fix before proceeding.
