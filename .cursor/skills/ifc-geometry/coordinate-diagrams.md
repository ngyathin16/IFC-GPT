# IFC4 Geometry — ASCII Coordinate Diagrams

## Coordinate System

```
         Z (up)
         │
         │
         │
         │
         └──────────── Y (north)
        /
       /
      X (east)
```

- **Units:** Meters (enforced by `IfcSIUnit`). All coordinates in meters.
- **Z-axis:** Up (gravity = -Z).
- **Origin:** `(0, 0, 0)` is at the southwest corner of the ground floor slab.
- **Rotation:** Counter-clockwise when viewed from above (right-hand rule).

---

## Wall Placement Geometry

```
                       thickness
                    ├──────────────┤
  start_point       ───────────────────────────────  end_point
    (x1, y1)       │              │                │  (x2, y2)
                   │  wall center │axis            │
                   │              │                │
                    ───────────────────────────────
                   ◄──────────── length ──────────►
                   │
                   │ height (extruded upward from Z)
                   │
```

**Rules:**
- Center axis runs from `start_point` to `end_point`.
- Thickness extends **equally on both sides** (half-thickness each side).
- Height extrudes **upward** from the Z-coordinate of start/end.
- Wall normal (outward face): rotated 90° CCW from direction vector.

---

## Door/Window Placement in Walls

```
  Wall start ──────────┬──────────┬───────────── Wall end
              distance  │  opening │
              along     │  width   │
              wall      │          │
              ──────────┴──────────┴─────────────
                        │  sill    │
                        │  height  │
  Floor Z ──────────────┴──────────┴─────────────
```

**Coordinate transform (wall-relative → global):**
```python
dx, dy = end[0]-start[0], end[1]-start[1]
length = sqrt(dx**2 + dy**2)
t = distance_along / length
global_x = start[0] + t * dx
global_y = start[1] + t * dy
global_z = storey_z + sill_height
```

---

## Slab Boundary (Plan View)

```
  [0,4] ──────────── [5,4]
    │                   │    Boundary polygon
    │   Slab interior   │    counter-clockwise from above
    │                   │    (normal = +Z)
  [0,0] ──────────── [5,0]
```

- Points are 2D `[x, y]`; Z from `location` parameter.
- Polygon must be **counter-clockwise** viewed from above.
- Slab extrudes **downward** from Z by `depth`.

---

## L-Junction Corner Overlap

```
         W2 (north)
           │  │
           │  │ thickness
           │  │
  W1 ──────┘  │
  ────────────┼──────────
              │
```

- Walls share an endpoint; corner geometry overlaps by `thickness/2`.
- Bonsai handles join cleanup at render time.
- Raw coordinate overlap is acceptable in v0.

---

## Multi-Storey Elevation Stacking

```
  Roof ─────────────── Z = 6.3m  (L1 elevation + wall height + roof thickness)
  ┌───────────────────┐
  │   First Floor     │    floor_to_floor = 3.0m
  │   (L1)            │    L1 walls at Z = 3.0m
  ├───────────────────┤─── Z = 3.0m  (L1 slab top)
  │   Ground Floor    │    floor_to_floor = 3.0m
  │   (GF)            │    GF walls at Z = 0.0m
  ├───────────────────┤─── Z = 0.0m  (GF slab top)
  │   Foundation      │    optional
  └───────────────────┘─── Z = -0.3m
```

**Elevation rules:**
- Storey elevation = Z of the **top of the floor slab** (walking surface).
- Wall `start_point.z` = storey elevation.
- Upper slab location.z = upper storey elevation (slab extrudes downward).
- Roof polyline Z = topmost storey elevation + wall height.

---

## Roof Overhang Positioning

```
  Wall footprint:  [0,0] to [5,4]
  Roof boundary:   [-0.3,-0.3] to [5.3,4.3]  (0.3m overhang each side)
  Roof Z:          wall_height + storey_elevation (= 3.0m for GF-only)
```

Standard overhang: **0.3m** on all sides for architectural correctness.
