---
name: ifc-geometry
description: >
  IFC4 coordinate system, wall placement geometry, multi-storey elevation stacking,
  and opening positioning math. Use when calculating coordinates, debugging geometry,
  or implementing coordinate transforms.
---

## IFC4 Coordinate System
- Right-handed: X=east, Y=north, Z=up
- Units: meters (set via IfcSIUnit)
- Origin: IfcSite local placement (usually 0,0,0)
- Rotation: counter-clockwise when viewed from above (right-hand rule)

## Wall Placement
- `create_two_point_wall(start, end, thickness, height)`
- Wall center axis = line from start→end
- Thickness extends **equally both sides** of axis (±thickness/2)
- Wall height: positive Z from start.z
- Corner overlap at L-junctions: `thickness/2` overlap in raw coordinates (Bonsai handles joins)

## Opening Positioning (Wall-Relative → Global)
Given: wall (start_point, end_point), distance_along_wall, sill_height, storey_elevation:
```python
dx = end[0] - start[0]
dy = end[1] - start[1]
wall_length = sqrt(dx**2 + dy**2)
t = distance_along_wall / wall_length
global_x = start[0] + t * dx
global_y = start[1] + t * dy
global_z = storey_elevation + sill_height
```

## Typical Sill Heights
- Doors: 0.0m (floor level)
- Windows: 0.9m–1.2m (standard residential)
- High windows (bathroom): 1.5m–1.8m
- Floor-to-ceiling windows: 0.0m

## Multi-Storey Z-Offsets
- Each IfcBuildingStorey has an elevation (Z-coordinate of floor walking surface)
- All elements on a storey placed at storey.elevation + local Z
- Stairs height = upper_storey.elevation - lower_storey.elevation
- Roof boundary Z = topmost_storey.elevation + wall_height

## Slab Boundary Rules
- Boundary points are 2D [x, y] — Z given by `location` parameter
- Points must be **counter-clockwise** viewed from above (normal points up)
- Slab extrudes **downward** from given Z by `depth`

## Elevation Stacking Example (2-storey)
```
Roof      Z = 6.3m  (L1 elevation + height + roof thickness)
L1 slab   Z = 3.0m  (floor_to_floor = 3.0m)
GF slab   Z = 0.0m  (ground level)
```

## Common Pitfalls
- Doors/windows use **global** coordinates, not wall-relative (must transform)
- Wall direction vector normalization required before t calculation
- Roof polyline must overhang walls by ~0.3m on each side for visual correctness

## Additional Resources
- For ASCII diagrams, see [coordinate-diagrams.md](coordinate-diagrams.md)
