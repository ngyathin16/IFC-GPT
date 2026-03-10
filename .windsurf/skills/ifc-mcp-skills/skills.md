# IFC Building Generation Skills — Lego-Brick MCP Tool Guide

> **Purpose**: Teach the LLM agent how to assemble IFC4 building models by
> calling MCP tools in the correct order, with correct parameters.  Each tool
> is a Lego brick — you stack them bottom-to-top, inside-out.

---

## 1. Mental Model: Spatial Hierarchy

Every IFC model must follow this containment tree **before any geometry is
created**:

```
IfcProject
  └─ IfcSite
       └─ IfcBuilding
            ├─ IfcBuildingStorey  [Ground Floor, Z=0.0]
            │    ├─ IfcWall  (exterior + interior)
            │    ├─ IfcSlab  (floor)
            │    ├─ IfcDoor  (hosted in wall)
            │    └─ IfcWindow (hosted in wall)
            ├─ IfcBuildingStorey  [Level 1, Z=floor_to_floor_height]
            │    └─ ... same elements ...
            └─ IfcRoof  (on topmost storey)
```

The Bonsai MCP server manages the Project/Site/Building/Storey scaffolding
automatically.  You manage everything **inside** the storeys.

---

## 2. Coordinate System

| Axis | Direction | Unit |
|------|-----------|------|
| X    | East      | metres |
| Y    | North     | metres |
| Z    | Up        | metres |

- Ground floor slab sits at **Z = 0**.
- Storey elevations stack: GF=0.0, L1=3.0, L2=6.0, etc.
- Wall `start_point` / `end_point` are **3-D** `[x, y, z]` where `z` = storey elevation.
- Opening positions are **3-D** `[x, y, z]` where `z` = storey_elevation + sill_height.

---

## 3. Build Sequence (MUST follow)

```
Phase A — Walls (storey by storey, ground first)
Phase B — Slabs (after walls on that storey are confirmed)
Phase C — Openings: doors first, then windows (after host walls exist)
Phase D — Stairs (after both connected storeys are complete)
Phase E — Roof (always last)
```

**Dependency rules:**
- B requires A on the same storey
- C requires the specific host wall from A
- D requires A on both the lower and upper storey
- E requires A on the topmost storey

---

## 4. Tool Reference

### 4.1 Wall Creation

```python
# Two-point wall (most common)
create_two_point_wall(
    start_point=[x1, y1, z],   # z = storey elevation
    end_point=[x2, y2, z],
    thickness=0.2,              # exterior walls: 0.2 m; interior: 0.15 m
    height=3.0,                 # floor-to-floor height
    name="W1"                   # matches wall_ref in BuildingPlan
)

# Polyline walls (for L-shaped or complex outlines in one call)
create_polyline_walls(
    points=[[0,0,0],[10,0,0],[10,8,0],[0,8,0],[0,0,0]],
    thickness=0.2,
    height=3.0
)
```

**Tips:**
- Corner walls must share exactly the same endpoint coordinates (no gap/overlap).
- For T-junctions, the intersecting wall's endpoint must touch the face of the
  continuous wall, not overlap it.
- Minimum wall length: 0.3 m.  Minimum thickness: 0.08 m.

---

### 4.2 Slab Creation

```python
create_slab(
    polyline=[[0,0],[10,0],[10,8],[0,8],[0,0]],  # 2-D boundary points
    depth=0.2,                                    # slab thickness
    location=[0, 0, 0.0],                        # [x_offset, y_offset, z_elevation]
    name="Slab_GF"
)
```

**Tips:**
- `polyline` is **2-D** `[x, y]` points; `location` z sets the elevation.
- Close the polygon (repeat first point, or it auto-closes).
- Slab boundary should align with the inside face of exterior walls.

---

### 4.3 Door Creation

```python
create_door(
    dimensions={"width": 0.9, "height": 2.1},
    operation_type="SINGLE_SWING_LEFT",  # or SINGLE_SWING_RIGHT, DOUBLE_DOOR_SINGLE_SWING
    location=[x, y, z]                   # z = storey elevation (sill = 0)
)
```

**operation_type enum:** `SINGLE_SWING_LEFT | SINGLE_SWING_RIGHT |
DOUBLE_DOOR_SINGLE_SWING | SLIDING_TO_LEFT | SLIDING_TO_RIGHT`

**Placement rules:**
- `location` must be on the wall centre-line.
- `z` = storey elevation (doors sit on the floor).
- Minimum clearance between door edge and wall corner: 0.1 m.

---

### 4.4 Window Creation

```python
create_window(
    dimensions={"width": 1.2, "height": 1.5},
    partition_type="SINGLE_PANEL",  # or DOUBLE_PANEL_VERTICAL, TRIPLE_PANEL_VERTICAL
    location=[x, y, z]              # z = storey_elevation + sill_height (typically 0.9)
)
```

**Placement rules:**
- `z` = storey_elevation + sill_height.  Typical sill: 0.9 m.
- Windows must not overlap doors on the same wall.
- Head height (z + height) must be ≤ storey elevation + wall_height − 0.1 m.

---

### 4.5 Roof Creation

```python
create_roof(
    polyline=[[0,0,3.0],[10,0,3.0],[10,8,3.0],[0,8,3.0],[0,0,3.0]],  # 3-D
    roof_type="FLAT",   # FLAT | SHED | GABLE_ROOF | HIP_ROOF
    angle=5.0,          # pitch angle in degrees (0 for flat)
    thickness=0.3
)
```

**Tips:**
- `polyline` points use the **topmost storey elevation** as their Z.
- For gable/hip roofs, `angle` drives the ridge height.
- Roof outline should match or slightly overhang the building footprint (0.3–0.6 m eave).

---

### 4.6 Stairs Creation

```python
create_stairs(
    width=1.2,
    height=3.0,         # total rise = upper_storey_elevation - lower_storey_elevation
    stairs_type="STRAIGHT"  # STRAIGHT | L_SHAPED | U_SHAPED | SPIRAL
)
```

**Tips:**
- `height` is the total rise between the two connected storeys.
- Stair opening in the slab above must be pre-cut (use a matching slab boundary
  that excludes the stair area, or `execute_ifc_code_tool` to add void).

---

### 4.7 Surface Styling (optional)

```python
# Create a named style
create_surface_style(
    name="ConcreteGrey",
    color=[0.6, 0.6, 0.6],   # RGB 0-1
    transparency=0.0
)

# Apply to an element by name
apply_style_to_object(
    object_name="W1",
    style_name="ConcreteGrey"
)
```

---

### 4.8 Query Tools (use freely, no side effects)

```python
get_ifc_scene_overview()          # full scene JSON — call before any repair
get_wall_properties(name="W1")    # returns thickness, height, area, psets
get_slab_properties(name="Slab_GF")
get_door_properties(name="Door_01")
get_window_properties(name="Win_01")
get_object_info(name="W1")        # GUID, type, placement, relationships
```

---

### 4.9 Repair / Update Tools (repair phase only)

```python
update_wall(name="W1", height=3.2, thickness=0.2)
update_slab(name="Slab_GF", depth=0.25)
update_door(name="Door_01", location=[x, y, z])
update_window(name="Win_01", location=[x, y, z])
update_roof(name="Roof_01", angle=10.0)
update_stairs(name="Stairs_01", width=1.4)

# For property-set / containment fixes
execute_ifc_code_tool(code="...ifcopenshell.api.run(...)...")
```

---

## 5. Common Mistakes and How to Avoid Them

| Mistake | Rule |
|---------|------|
| Wall endpoints don't meet exactly | Use identical `[x, y, z]` tuples for shared corners |
| Opening outside wall boundary | Check `distance_along_wall < wall_length - opening_width/2` |
| Slab not at correct elevation | `location` z must equal storey elevation, not 0 |
| Roof created before walls | Always last — after all walls, slabs, openings, stairs |
| Door z ≠ storey elevation | Doors always at `z = storey_elevation`, sill = 0 |
| Window head above wall top | Check `sill_height + window_height < wall_height - 0.1` |
| Stairs created before upper storey walls | D depends on A for both storeys |
| Duplicate element names | Every `name` param must be unique across the whole model |

---

## 6. Parallel Subagent Decomposition Pattern

When building multi-storey structures, decompose into four concurrent subagents:

```
┌─────────────────────────────────────────────────────┐
│  Subagent A (Structure)                             │
│    GF walls → L1 walls → … (bottom-to-top)         │
├─────────────────────────────────────────────────────┤
│  Subagent B (Slabs) — starts after A confirms GF   │
│    GF slab → L1 slab → …                           │
├─────────────────────────────────────────────────────┤
│  Subagent C (Openings) — starts after A confirms   │
│    each wall; doors then windows per storey         │
├─────────────────────────────────────────────────────┤
│  Subagent D (Vertical + Roof) — starts after A+B  │
│    confirm both storeys; stairs then roof           │
└─────────────────────────────────────────────────────┘
```

Each subagent communicates completion status via the shared `tool_calls_log`
in `AgentState`.  The coordinator checks the log before gating the next phase.

---

## 7. Validation Checklist (run after every build)

The pipeline runs these automatically, but you can pre-check mentally:

- [ ] Every element has a storey container (`IfcRelContainedInSpatialStructure`)
- [ ] Every door/window has a host wall (`IfcRelFillsElement`)
- [ ] Every exterior wall has `Pset_WallCommon.IsExternal = True`
- [ ] Every interior wall has `Pset_WallCommon.IsExternal = False`
- [ ] Every slab has `Pset_SlabCommon.IsExternal = False`
- [ ] No zero-thickness walls
- [ ] No self-intersecting slab boundaries
- [ ] No floating openings (door/window outside wall bbox)
- [ ] Roof outline encloses the entire building footprint

---

## 8. IFC Code Snippets for Common Repairs

### Add missing Pset_WallCommon
```python
import ifcopenshell
import ifcopenshell.api
ifc = ifcopenshell.open("/path/to/model.ifc")
wall = ifc.by_guid("GUID_HERE")
pset = ifcopenshell.api.run("pset.add_pset", ifc, product=wall, name="Pset_WallCommon")
ifcopenshell.api.run("pset.edit_pset", ifc, pset=pset,
                     properties={"IsExternal": True, "LoadBearing": False})
ifc.write("/path/to/model.ifc")
```

### Assign element to storey
```python
ifc = ifcopenshell.open("/path/to/model.ifc")
element = ifc.by_guid("GUID_HERE")
storey = next(s for s in ifc.by_type("IfcBuildingStorey") if s.Name == "Ground Floor")
ifcopenshell.api.run("spatial.assign_container", ifc,
                     relating_structure=storey, products=[element])
ifc.write("/path/to/model.ifc")
```
