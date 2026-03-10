---
trigger: always_on
---

## IFC Vertical Circulation Rules (Stairs, Lifts, Ramps)

Vertical circulation is the most common source of "common-sense" failures in generated
IFC models. A building with N storeys **must** provide continuous vertical access between
ALL storeys. Apply these rules at the `plan` stage before any geometry is created.

---

### 1. Stair Continuity Requirement

- A building with **N storeys** requires stairs (or other vertical circulation) that
  connect **all N storeys** — from Ground (storey 0) to the top storey (storey N-1).
- **Do not** create stairs only from Ground to Storey 1 and leave upper floors inaccessible.
- Each inter-storey connection (e.g., Ground→1, 1→2, 2→3 …) must be explicitly modelled with a dedicated `IfcStair` element placed in the appropriate storey.

---

### 2. Stair Placement Per Storey

- Place one stair flight per inter-storey transition:
  - `create_stairs(height = storey_height, location = [stair_x, stair_y, storey_elevation])`
  - The stair's `location.z` must equal the `Elevation` of the lower storey.
- The stair at storey N connects storey N to storey N+1; its top landing z-coordinate must equal `storey[N+1].Elevation`.

---

### 3. Stair Geometry Rules

- **Riser height**: 0.15 m – 0.22 m (IBC/Building Regs compliant range).
- **Tread depth (going)**: 0.25 m – 0.33 m.
- **Stair width**: minimum 0.9 m (residential), 1.2 m (commercial/public).
- **Headroom clearance**: minimum 2.0 m above every tread nosing and landing.
- Auto-calculated `num_steps = ceil(storey_height / riser_height)`; preferred riser ≈ 0.175 m.

#### Implementation — `IfcStairFlight` geometry

Use `ShapeBuilder` to build a **stepped profile extruded in the width direction**.
Import lazily inside the function to avoid circular imports:

```python
from ifcopenshell.util.shape_builder import ShapeBuilder  # lazy import
builder = ShapeBuilder(ifc)

num_risers = 9  # ceil(storey_height / riser_h)
riser_h = storey_height / num_risers
tread_d = 0.260
run_length = num_risers * tread_d

pts_2d = [(0.0, 0.0)]
for i in range(num_risers):
    x0, z0 = i * tread_d, i * riser_h
    pts_2d.append((x0, z0 + riser_h))            # up riser
    pts_2d.append((x0 + tread_d, z0 + riser_h)) # across tread
pts_2d.append((run_length, 0.0))                 # back to ground

profile   = builder.polyline(pts_2d, closed=True)
extrusion = builder.extrude(
    profile, magnitude=width,
    position_x_axis=(1.0, 0.0, 0.0),
    extrusion_vector=(0.0, 1.0, 0.0),
)
rep = ifc.createIfcShapeRepresentation(body_ctx, "Body", "SweptSolid", [extrusion])
ifcopenshell.api.run("geometry.assign_representation", ifc, product=stair, representation=rep)
```

**Do NOT** use a flat mesh box or a simple `add_slab_representation` for stairs — they render as invisible or incorrectly shaped solids in IFC viewers.

---

### 4. Stair Core / Stairwell

- Every stair must be enclosed by walls forming a **stair core** — open staircases floating in space are only valid if the brief explicitly asks for an open-plan stair.
- The stair core walls must span the full height of the storey in which the stair is placed.
- Leave a clear opening in the floor slab above the stair (`create_opening()` on the slab) so the stair connects the levels geometrically.

#### Stair core wall layout

For a corner core (e.g., NW at `x: 0–3, y: 12–15` in a 20 × 15 m plan):
- The **building perimeter** provides the north and west walls — do not duplicate them.
- Add a **south wall** at `y = core_south_y` spanning the core width.
- Add an **east wall** (NW core) or **west wall** (NE core) closing the open interior side.
- This function must be called for **every storey** (offices, residential, plant) — not just the ground floor.

```python
def _build_stair_core_walls(ifc, storey, storey_ref, elev, height, body_ctx, axis_ctx):
    CORE_W, CORE_Y = 3.0, DEPTH - 3.0  # 3 m wide, south face at y=12
    # NW core: south + east closing walls
    _create_wall(ifc, storey, f"{storey_ref}_StairNW_S", False,
                 start=[0.0, CORE_Y], end=[CORE_W, CORE_Y], ...)
    _create_wall(ifc, storey, f"{storey_ref}_StairNW_E", False,
                 start=[CORE_W, CORE_Y], end=[CORE_W, DEPTH], ...)
    # NE core: south + west closing walls
    _create_wall(ifc, storey, f"{storey_ref}_StairNE_S", False,
                 start=[WIDTH - CORE_W, CORE_Y], end=[WIDTH, CORE_Y], ...)
    _create_wall(ifc, storey, f"{storey_ref}_StairNE_W", False,
                 start=[WIDTH - CORE_W, DEPTH], end=[WIDTH - CORE_W, CORE_Y], ...)
```

---

### 5. Multiple Stairs and Lifts

- For buildings > 4 storeys above ground OR > 2 storeys below ground: include **at least one lift** (`IfcTransportElement` with `PredefinedType = ELEVATOR`) in addition to the stairs.
- For buildings > 8 storeys: minimum **two independent stair cores** for fire safety compliance.
- Lifts must also span ALL storeys they serve — model a lift shaft that is a continuous vertical volume.

---

### 6. Ramps

- A ramp is required wherever `stairs_type = "STRAIGHT"` would be inaccessible (wheelchair access routes, car parks, service routes).
- Ramp gradient must not exceed **1:12 (8.3 %)** for accessible routes or **1:6 (16.7 %)** for service ramps.
- Model ramps as `IfcRamp` with `PredefinedType = STRAIGHT_RUN_RAMP` or similar.

---

### 7. Pre-build Planning Checklist

Before calling any `create_stairs()`:

1. Count total storeys from `BuildingPlan.num_storeys`.
2. List ALL inter-storey transitions: `[(0→1), (1→2), …, (N-2→N-1)]`.
3. For each transition, confirm stair parameters:
   - `height` = `floor_to_floor_height` (typically 3.0 m–4.5 m).
   - `location.z` = elevation of lower storey.
   - `location.x, .y` = stair core position (consistent across all storeys).
4. Generate stairs for **every transition** — never skip a floor.

---

### 8. Post-build Verification

After building stairs:

1. `get_ifc_scene_overview()` → count `IfcStairFlight` instances. Must equal `(num_storeys - 1) × num_cores` (minimum).
   - Two stair cores in a 10-storey building → 18 `IfcStairFlight` instances.
2. For each stair flight, verify `location.z` matches the expected lower storey elevation.
3. Confirm no storey is unreachable: every storey must have at least one stair bottom or stair top landing at its elevation.
4. Open the IFC in a viewer and confirm stair flights are **visible as stepped solids**, not flat boxes or invisible elements.
