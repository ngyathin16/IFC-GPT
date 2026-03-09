---
trigger: glob
glob: "**/*.py"
---

## Python Rules

- Python 3.10+ with type hints on every function signature and class attribute.
- Every module (`.py` file) must begin with a module-level docstring describing its purpose.
- Use `ifcopenshell.api` for all IFC operations. Raw entity manipulation (`model.create_entity`, direct attribute assignment) is forbidden unless no API equivalent exists, and must be justified with an inline comment.
- **Environment discipline**: MCP server code runs in the system/venv environment. Blender addon code runs in Blender's embedded Python. Never import system packages inside Blender addon code or vice versa.
- Use `uv` for dependency management. Do not call `pip install` directly; update `pyproject.toml` instead.
- No secrets or API keys in source files. Use `.env` + `python-dotenv`.
