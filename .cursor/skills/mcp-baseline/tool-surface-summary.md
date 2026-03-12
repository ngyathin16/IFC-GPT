# Tool Surface Summary (Appendix A)

The `ifc-bonsai-mcp` server exposes **52 tools** across 3 modules. Source: `docs/api-reference.md`.

## Analysis Tools (2 tools) — `analysis_tools.py`

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `capture_blender_window_screenshot` | Full Blender window screenshot | `max_size`, `format`, `quality` |
| `capture_blender_3dviewport_screenshot` | 3D viewport only (no UI) | `max_size`, `shading_type`, `deterministic` |

## API Tools (42 tools) — `api_tools.py`

### Scene Inspection (6 tools)

| Tool | Purpose |
|------|--------|
| `get_scene_info` | List all Blender objects with IFC GUIDs, supports pagination |
| `get_blender_object_info` | Detailed info for specific Blender object |
| `get_selected_objects` | Currently selected objects with GUIDs |
| `get_object_info` | IFC info by GUIDs or selection, with properties/relationships |
| `get_ifc_scene_overview` | Project info, units, spatial hierarchy, element counts |
| `list_ifc_entities` | Valid IFC entity classes for current schema |

### Wall Operations (5 tools)

| Tool | Key Parameters |
|------|---------------|
| `create_wall` | `name`, `dimensions` (length/height/thickness), `location`, `rotation`, `material` |
| `create_two_point_wall` | `start_point`, `end_point`, `thickness`, `height` |
| `create_polyline_walls` | `points` (list of 3D coords), `closed`, `thickness`, `height` |
| `update_wall` | `wall_guid`, `dimensions`, `geometry_properties` |
| `get_wall_properties` | `wall_guid` → name, dimensions, direction_sense, offset |

### Slab Operations (3 tools)

| Tool | Key Parameters |
|------|---------------|
| `create_slab` | `polyline` (2D points), `depth`, `location`, `material` |
| `update_slab` | `slab_guid`, `depth`, `polyline`, `geometry_properties` |
| `get_slab_properties` | `slab_guid` → depth, boundary, materials |

### Door Operations (4 tools)

| Tool | Key Parameters |
|------|---------------|
| `get_door_operation_types` | Returns: SINGLE_SWING_LEFT/RIGHT, DOUBLE_DOOR_*, SLIDING_* |
| `create_door` | `dimensions` (width/height), `operation_type`, `location`, `frame_properties`, `panel_properties` |
| `update_door` | `door_guid`, `dimensions`, `operation_type`, `frame_properties` |
| `get_door_properties` | `door_guid` → width, height, operation_type, lining_props |

### Window Operations (4 tools)

| Tool | Key Parameters |
|------|---------------|
| `get_window_partition_types` | Returns: SINGLE_PANEL, DOUBLE_PANEL_*, TRIPLE_PANEL_* |
| `create_window` | `dimensions` (width/height), `partition_type`, `location`, `wall_guid`, `create_opening` |
| `update_window` | `window_guid`, `dimensions`, `partition_type`, `frame_properties` |
| `get_window_properties` | `window_guid` → dimensions, partition_type, frame_properties |

### Roof Operations (4 tools)

| Tool | Key Parameters |
|------|---------------|
| `get_roof_types` | Returns: FLAT, SHED, GABLE_ROOF, HIP_ROOF, MANSARD, DOME, etc. |
| `create_roof` | `polyline` (3D outline), `roof_type`, `angle`, `thickness` |
| `update_roof` | `roof_guid`, `roof_type`, `angle`, `thickness` |
| `delete_roof` | `roof_guids` (batch delete) |

### Stairs Operations (4 tools)

| Tool | Key Parameters |
|------|---------------|
| `get_stairs_types` | Returns: STRAIGHT, SPIRAL, L_SHAPED, U_SHAPED |
| `create_stairs` | `width`, `height`, `stairs_type`, `num_steps`, `length`, `radius` |
| `update_stairs` | `stairs_guid`, `width`, `height`, `stairs_type` |
| `delete_stairs` | `stairs_guids` (batch delete) |

### Style Operations (6 tools)

| Tool | Key Parameters |
|------|---------------|
| `create_surface_style` | `name`, `color` [R,G,B], `transparency`, `style_type` |
| `create_pbr_style` | `name`, `diffuse_color`, `metallic`, `roughness`, `emissive_color` |
| `apply_style_to_object` | `object_guids` (batch), `style_name` |
| `list_styles` | Lists all styles with colors and properties |
| `update_style` | `style_name`, `color`, `transparency`, `metallic`, `roughness` |
| `remove_style` | `style_name` |

### Code Execution & Mesh (6 tools)

| Tool | Key Parameters |
|------|---------------|
| `execute_blender_code` | `code` — arbitrary Blender Python (⚠️ security risk) |
| `execute_ifc_code_tool` | `code` — sandboxed IfcOpenShell code (safer) |
| `create_mesh_ifc` | `items` (vertices/faces), `ifc_class`, `placement` |
| `create_trimesh_ifc` | `trimesh_code`, `ifc_class`, `location`, `parameters` |
| `list_blender_commands` | Lists available Blender addon commands |
| `get_trimesh_examples` | Example code for architectural elements |

## RAG Tools (8 tools) — `rag_tools.py`

| Tool | Purpose |
|------|--------|
| `ensure_ifc_knowledge_ready` | Initialize knowledge system (call first) |
| `search_ifc_knowledge` | Semantic search: query, context_type, module, max_results |
| `get_ifc_knowledge_status` | System readiness and cache stats |
| `find_ifc_function` | Search by operation + object_type + module |
| `get_ifc_module_info` | Module description, function list |
| `get_ifc_function_details` | Full function docs, signature, parameters, examples |
| `clear_ifc_knowledge_cache` | Clear performance caches |
| `get_cache_statistics` | Cache usage and system stats |
