/**
 * Converts a Pascal editor scene (Zustand store snapshot) into an
 * IFC-GPT BuildingPlan JSON object compatible with /api/build-from-plan.
 *
 * Pascal node types used:
 *   - level  → StoreyDefinition
 *   - wall   → WallPlacement
 *   - slab   → SlabPlacement
 *   - item (door/window) → OpeningPlacement
 *   - roof   → RoofPlacement
 */

export interface StoreyDefinition {
  storey_ref: string;
  name: string;
  elevation: number;
  floor_to_floor_height: number;
}

export interface WallPlacement {
  element_type: "wall";
  wall_ref: string;
  component_id: "exterior_wall" | "interior_wall";
  storey_ref: string;
  start_point: [number, number];
  end_point: [number, number];
  height?: number;
  thickness?: number;
}

export interface OpeningPlacement {
  element_type: "door" | "window";
  component_id: "standard_door" | "standard_window";
  storey_ref: string;
  host_wall_ref: string;
  distance_along_wall: number;
  sill_height: number;
  width?: number;
  height?: number;
}

export interface SlabPlacement {
  element_type: "slab";
  component_id: "ground_slab";
  storey_ref: string;
  boundary_points: [number, number][];
  depth?: number;
}

export interface RoofPlacement {
  element_type: "roof";
  component_id: "flat_roof";
  storey_ref: string;
  boundary_points: [number, number, number][];
  roof_type: string;
  angle: number;
}

export type ElementPlacement = WallPlacement | OpeningPlacement | SlabPlacement | RoofPlacement;

export interface BuildingPlan {
  description: string;
  site: { name: string };
  building: { name: string; building_type: string };
  storeys: StoreyDefinition[];
  elements: ElementPlacement[];
  wall_junctions: any[];
  rooms: any[];
}

/**
 * Compute distance from a 2D point to the start of a wall segment.
 * Used to convert absolute door/window positions to parametric wall-distance.
 */
function distanceAlongWall(
  wallStart: [number, number],
  wallEnd: [number, number],
  point: [number, number]
): number {
  const dx = wallEnd[0] - wallStart[0];
  const dy = wallEnd[1] - wallStart[1];
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len === 0) return 0;
  // Project point onto wall axis
  const t = ((point[0] - wallStart[0]) * dx + (point[1] - wallStart[1]) * dy) / (len * len);
  return Math.max(0, Math.min(len, t * len));
}

export function sceneToBuildingPlan(nodes: Record<string, any>): BuildingPlan {
  const allNodes = Object.values(nodes);

  const levels = allNodes.filter((n) => n.type === "level").sort((a, b) => a.elevation - b.elevation);
  const walls = allNodes.filter((n) => n.type === "wall");
  const slabs = allNodes.filter((n) => n.type === "slab");
  const roofs = allNodes.filter((n) => n.type === "roof");
  // Pascal stores doors/windows as Item nodes with an itemType field
  const doors = allNodes.filter((n) => n.type === "item" && n.itemType === "door");
  const windows = allNodes.filter((n) => n.type === "item" && n.itemType === "window");

  const storeys: StoreyDefinition[] = levels.map((l) => ({
    storey_ref: l.id,
    name: l.name || `Level ${l.elevation}m`,
    elevation: l.elevation ?? 0,
    floor_to_floor_height: l.height ?? 3.0,
  }));

  const wallElements: WallPlacement[] = walls.map((w) => ({
    element_type: "wall",
    wall_ref: w.id,
    component_id: w.isExterior ? "exterior_wall" : "interior_wall",
    storey_ref: w.parentId ?? (levels[0]?.id || "GF"),
    start_point: [w.start?.[0] ?? 0, w.start?.[1] ?? 0],
    end_point: [w.end?.[0] ?? 1, w.end?.[1] ?? 0],
    height: w.height ?? undefined,
    thickness: w.thickness ?? undefined,
  }));

  // Build a wall lookup for door/window placement
  const wallById: Record<string, WallPlacement> = {};
  wallElements.forEach((w) => { wallById[w.wall_ref] = w; });

  const doorElements: OpeningPlacement[] = doors.map((d) => {
    const hostWall = wallById[d.hostWallId] ?? wallElements[0];
    const dist = hostWall
      ? distanceAlongWall(hostWall.start_point, hostWall.end_point, [d.position?.[0] ?? 0, d.position?.[1] ?? 0])
      : 0;
    return {
      element_type: "door",
      component_id: "standard_door",
      storey_ref: d.parentId ?? (levels[0]?.id || "GF"),
      host_wall_ref: d.hostWallId ?? (wallElements[0]?.wall_ref || "W1"),
      distance_along_wall: dist,
      sill_height: 0,
      width: d.width ?? undefined,
      height: d.height ?? undefined,
    };
  });

  const windowElements: OpeningPlacement[] = windows.map((w) => {
    const hostWall = wallById[w.hostWallId] ?? wallElements[0];
    const dist = hostWall
      ? distanceAlongWall(hostWall.start_point, hostWall.end_point, [w.position?.[0] ?? 0, w.position?.[1] ?? 0])
      : 1;
    return {
      element_type: "window",
      component_id: "standard_window",
      storey_ref: w.parentId ?? (levels[0]?.id || "GF"),
      host_wall_ref: w.hostWallId ?? (wallElements[0]?.wall_ref || "W1"),
      distance_along_wall: dist,
      sill_height: w.sillHeight ?? 0.9,
      width: w.width ?? undefined,
      height: w.height ?? undefined,
    };
  });

  const slabElements: SlabPlacement[] = slabs.map((s) => ({
    element_type: "slab",
    component_id: "ground_slab",
    storey_ref: s.parentId ?? (levels[0]?.id || "GF"),
    boundary_points: (s.boundary ?? []).map((p: number[]) => [p[0], p[1]] as [number, number]),
    depth: s.depth ?? undefined,
  }));

  const roofElements: RoofPlacement[] = roofs.map((r) => ({
    element_type: "roof",
    component_id: "flat_roof",
    storey_ref: r.parentId ?? (levels[levels.length - 1]?.id || "RF"),
    boundary_points: (r.boundary ?? []).map((p: number[]) => [p[0], p[1], p[2] ?? 0] as [number, number, number]),
    roof_type: r.roofType ?? "FLAT",
    angle: r.angle ?? 5.0,
  }));

  return {
    description: "Building plan from visual editor",
    site: { name: "Default Site" },
    building: { name: "Building A", building_type: "Mixed-use" },
    storeys,
    elements: [...wallElements, ...slabElements, ...doorElements, ...windowElements, ...roofElements],
    wall_junctions: [],
    rooms: [],
  };
}
