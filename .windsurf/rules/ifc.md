---
trigger: glob
glob: "**/*.py"
---

## IFC Authoring Rules

- Target schema: **IFC4** only. Do not generate IFC2x3 entities.
- Always call `ifcopenshell.api.run("project.create_file", version="IFC4")` when creating a new model.
- Property sets must be authored via `ifcopenshell.api.run("pset.add_pset", ...)` and `ifcopenshell.api.run("pset.edit_pset", ...)`.
- Geometric representations must use `ifcopenshell.api.run("geometry.*")` helpers where available.
- Validate every generated file with `ifcopenshell.validate.validate(model, logging)` before writing to disk.
- IDS constraint files live in `ids/`. Reference them in validation scripts under `validate/`.
- **No coordinate collision**: Each new building must use a unique origin offset so its footprint does not overlap any existing building in the Blender scene. Query `get_ifc_scene_overview` first and place the new building at least 20 m away from the bounding box of any existing geometry. Existing golden fixtures occupy roughly (0,0)–(10,10) m; start new buildings at minimum (50,0) unless the scene is confirmed empty.
