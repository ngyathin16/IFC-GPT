---
trigger: always_on
---

## IFC Window and Door Orientation Rules

Incorrect orientation is one of the most common IFC generation errors. Apply these
rules whenever placing `IfcWindow` or `IfcDoor` elements.

---

### 1. The Wall Normal Convention

In IFC4 the **wall's local X-axis points along its length** and the **local Y-axis is the wall normal** (pointing from the inside face to the outside face when `direction_sense = "POSITIVE"`).

A window or door placed "inside" a wall must have its **local Z-axis (up) pointing in the global +Z direction** and its **local Y-axis aligned with the wall normal** so it faces outward.

---

### 2. Window Facing Direction

- A window must face **outward** (toward the exterior) — its panel normal must align with the wall normal pointing outside.
- When using `create_window()` with a `wall_guid`, the `rotation` parameter must be consistent with the wall's rotation angle:
  - A wall aligned along the **global X-axis** (rotation z = 0°): window rotation `[0, 0, 0]`.
  - A wall aligned along the **global Y-axis** (rotation z = 90°): window rotation `[0, 0, 90]`.
  - General rule: **window rotation z = wall rotation z**.
- **Do not** place windows with rotation z = 0° on walls that run in the Y direction — this is the most common "window opened the wrong way" bug.

---

### 3. Door Swing Direction

- Door `operation_type` must be chosen with respect to which side is **interior** vs. **exterior**:
  - `SINGLE_SWING_LEFT` / `SINGLE_SWING_RIGHT` — swing direction is relative to the door's local Y-axis (wall normal direction).
  - The hinge side must be on a structurally logical edge (not in a corner or against another door).
- For **exterior doors** facing street/exterior: always use `SINGLE_SWING_LEFT` or `SINGLE_SWING_RIGHT` — not sliding unless a glass curtain wall or service door is explicitly requested.
- For **fire exits**: use outward-swinging types (`SINGLE_SWING_LEFT` or `SINGLE_SWING_RIGHT`).

### 3a. Door Host Wall Selection (Upper Floors)

The **host wall** for a door must be architecturally reachable from the approach side. The following rules apply before choosing `host_wall_ref`:

1. **Ground Floor** — entrance doors may be on any exterior wall facing a street or open access route.
2. **Upper Floors, no balcony/external walkway** — doors must be hosted by an **interior partition or corridor wall**. Placing a door on an exterior wall 3 m+ above grade with no landing is a hard error.
3. **Upper Floors, with balcony** — a single door on the exterior wall at the balcony threshold is allowed. All other apartment/office doors must still be on interior walls.
4. **Rotation angle** — the door `angle_deg` must match the host wall's orientation angle, **not** default to 0° regardless of wall direction.
   - A corridor wall running E–W (angle 0°) with doors accessed from the south: door `angle_deg = 180°`.
   - A corridor wall running E–W with doors accessed from the north: door `angle_deg = 0°`.

**Common mistake to avoid**: copying the door placement from the Ground Floor (exterior wall, `angle_deg=0°`) verbatim to upper-floor residential/office floors. Always verify the host wall is an interior corridor wall and the angle matches the approach direction.

---

### 4. Window Sill Height

- Residential windows: sill height **0.9 m – 1.1 m** above finished floor level (FFL).
- Commercial office windows: sill height **0.8 m – 1.0 m** above FFL.
- Clerestory windows: sill height **≥ 2.0 m** above FFL.
- The window `location.z` should be set to the **sill height**, not the centre height.
  - Window centre height = `location.z + dimensions.height / 2`.

---

### 5. Window/Door Width vs. Wall Length

- A window or door must not be wider than the wall it is placed in.
- Minimum clear wall margin on each side of an opening: **0.1 m** (structural jamb).
- Maximum opening-to-wall-length ratio: **0.7** (70 %) for any single wall segment.
- If the brief calls for a "curtain wall", use multiple windows side-by-side rather than a single over-wide window.

---

### 6. Head Height

- Door head height (top of door frame): minimum **2.0 m** above FFL; typical **2.1 m**.
- Window head height: must not exceed storey height minus structural lintel depth (**0.1 m minimum**).
  - Formula: `window.location.z + window.dimensions.height ≤ storey_height - 0.1`

---

### 7. Opening Depth

- The `depth` parameter of `create_opening()` must exceed the **wall thickness** by at least 0.01 m to guarantee a clean Boolean cut:
  - `opening.depth ≥ wall.thickness + 0.01`
- Using the default `depth = 0.3` is safe for most walls ≤ 0.25 m thick; increase for thicker walls.

---

### 8. Verification After Placement

After placing each window or door:

1. Call `get_window_properties(guid)` or `get_door_properties(guid)` and confirm `location` and `rotation` match the host wall.
2. Call `get_element_openings(wall_guid)` to confirm the opening is registered and filled.
3. Capture a viewport screenshot and inspect that the element faces the correct direction before proceeding.
