"""BuildingPlan schema — the JSON contract between LLM planner and executor.

This module defines the Pydantic models that the LLM's generate_plan node
must output. The executor node deserializes this JSON and translates each
ElementPlacement into a sequence of MCP tool calls.

Design principles:
- Every field has a concrete type and sensible default where possible.
- The LLM only needs to reason about architectural intent; the executor
  handles coordinate transforms and tool-call sequencing.
- Wall references use deterministic IDs (wall_ref) so openings can
  reference their host wall before it has an IFC GUID.
"""
from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Spatial Structure
# ---------------------------------------------------------------------------


class SiteInfo(BaseModel):
    """Top-level site metadata."""

    name: str = Field(default="Default Site", description="Site name")
    latitude: Optional[float] = Field(default=None, description="WGS84 latitude")
    longitude: Optional[float] = Field(default=None, description="WGS84 longitude")


class BuildingInfo(BaseModel):
    """Building-level metadata."""

    name: str = Field(default="Building A", description="Building name")
    building_type: Optional[str] = Field(
        default=None,
        description="E.g. 'Residential', 'Commercial', 'Mixed-use'",
    )


class StoreyDefinition(BaseModel):
    """Defines one storey in the building.

    The elevation is the Z-coordinate of the storey's floor level.
    All elements on this storey are placed relative to this elevation.
    """

    storey_ref: str = Field(
        description="Local reference ID, e.g. 'GF', 'L1', 'L2'. "
        "Used by ElementPlacement.storey_ref to assign elements.",
    )
    name: str = Field(description="Display name, e.g. 'Ground Floor'")
    elevation: float = Field(
        description="Floor elevation in meters (Z-coordinate). "
        "Ground floor is typically 0.0.",
    )
    floor_to_floor_height: float = Field(
        default=3.0,
        description="Total height from this floor to the next floor (meters). "
        "Used to derive wall heights.",
    )


# ---------------------------------------------------------------------------
# Element Placement Instructions
# ---------------------------------------------------------------------------


class WallPlacement(BaseModel):
    """Instruction to place a wall."""

    element_type: Literal["wall"] = "wall"
    wall_ref: str = Field(
        description="Local reference ID for this wall, e.g. 'W1', 'W2'. "
        "Doors/windows use this to reference their host wall.",
    )
    component_id: Literal["exterior_wall", "interior_wall"] = Field(
        description="Component ID from registry.yaml",
    )
    storey_ref: str = Field(description="Which storey this wall belongs to")
    start_point: List[float] = Field(
        description="[x, y] start point in meters (2D, Z derived from storey elevation)",
    )
    end_point: List[float] = Field(
        description="[x, y] end point in meters (2D, Z derived from storey elevation)",
    )
    height: Optional[float] = Field(
        default=None,
        description="Wall height override. If None, uses storey floor_to_floor_height.",
    )
    thickness: Optional[float] = Field(
        default=None,
        description="Wall thickness override. If None, uses registry default.",
    )

    @field_validator("start_point", "end_point")
    @classmethod
    def validate_2d_point(cls, v: List[float]) -> List[float]:
        """Ensure the point is a 2-element [x, y] list."""
        if len(v) != 2:
            raise ValueError(f"Expected 2D point [x, y], got {len(v)} coordinates")
        return v


class OpeningPlacement(BaseModel):
    """Instruction to place a door or window in a wall."""

    element_type: Literal["door", "window"]
    component_id: Literal["standard_door", "standard_window"] = Field(
        description="Component ID from registry.yaml",
    )
    storey_ref: str = Field(description="Which storey this opening belongs to")
    host_wall_ref: str = Field(
        description="wall_ref of the wall this opening is cut into",
    )
    distance_along_wall: float = Field(
        description="Distance in meters from wall start_point to center of opening, "
        "measured along the wall axis.",
    )
    sill_height: float = Field(
        default=0.0,
        description="Height from floor to bottom of opening. "
        "Doors: 0.0. Windows: typically 0.9-1.2m.",
    )
    width: Optional[float] = Field(default=None, description="Override width")
    height: Optional[float] = Field(default=None, description="Override height")
    operation_type: Optional[str] = Field(
        default=None,
        description="Door operation type, e.g. 'SINGLE_SWING_LEFT'",
    )
    partition_type: Optional[str] = Field(
        default=None,
        description="Window partition type, e.g. 'SINGLE_PANEL'",
    )


class SlabPlacement(BaseModel):
    """Instruction to place a floor slab."""

    element_type: Literal["slab"] = "slab"
    component_id: Literal["ground_slab"] = "ground_slab"
    storey_ref: str = Field(description="Which storey this slab belongs to")
    boundary_points: List[List[float]] = Field(
        description="2D boundary polygon [[x,y], ...] in meters. "
        "Must be closed (first point repeated or auto-closed).",
    )
    depth: Optional[float] = Field(default=None, description="Slab depth override")


class RoofPlacement(BaseModel):
    """Instruction to place a roof."""

    element_type: Literal["roof"] = "roof"
    component_id: Literal["flat_roof"] = "flat_roof"
    storey_ref: str = Field(description="Which storey this roof is on (topmost)")
    boundary_points: List[List[float]] = Field(
        description="3D outline points [[x,y,z], ...] defining roof boundary",
    )
    roof_type: str = Field(default="FLAT")
    angle: float = Field(default=5.0)
    thickness: Optional[float] = Field(default=None)


class StairsPlacement(BaseModel):
    """Instruction to place stairs between storeys."""

    element_type: Literal["stairs"] = "stairs"
    component_id: Literal["straight_stairs"] = "straight_stairs"
    storey_ref: str = Field(description="Lower storey that stairs originate from")
    target_storey_ref: str = Field(description="Upper storey that stairs lead to")
    location: List[float] = Field(
        description="[x, y] position of stair start in meters",
    )
    width: float = Field(default=1.2)
    stairs_type: str = Field(default="STRAIGHT")


ElementPlacement = Union[
    WallPlacement,
    OpeningPlacement,
    SlabPlacement,
    RoofPlacement,
    StairsPlacement,
]


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


class WallJunction(BaseModel):
    """Declares that two walls meet at a junction point.

    This is used by the executor to ensure wall endpoints are coincident
    and to apply correct join geometry.
    """

    wall_ref_a: str
    wall_ref_b: str
    junction_type: Literal["L", "T", "X", "corner"] = Field(
        default="L",
        description="L=corner, T=wall meets mid-wall, X=cross",
    )


class RoomDefinition(BaseModel):
    """Optional: declares a named room bounded by walls.

    Used for semantic labeling and spatial zone assignment.
    Not strictly required for IFC generation but improves model quality.
    """

    name: str = Field(description="Room name, e.g. 'Living Room'")
    storey_ref: str
    bounding_wall_refs: List[str] = Field(
        description="Ordered list of wall_refs forming the room perimeter",
    )
    area_sqm: Optional[float] = Field(
        default=None, description="Expected floor area for validation"
    )


# ---------------------------------------------------------------------------
# Top-Level BuildingPlan
# ---------------------------------------------------------------------------


class BuildingPlan(BaseModel):
    """The complete building plan — output of the LLM planner, input to executor.

    This is the single JSON document that flows from the `generate_plan` node
    to the `execute_build_steps` node in the LangGraph pipeline.
    """

    plan_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:8],
        description="Unique plan identifier",
    )
    description: str = Field(
        description="Human-readable summary of what this plan creates",
    )

    site: SiteInfo = Field(default_factory=SiteInfo)
    building: BuildingInfo = Field(default_factory=BuildingInfo)
    storeys: List[StoreyDefinition] = Field(
        description="Ordered list of storeys (bottom to top)",
    )

    elements: List[ElementPlacement] = Field(
        description="All building elements to create, in execution order",
    )

    wall_junctions: List[WallJunction] = Field(
        default_factory=list,
        description="Declared wall-to-wall junctions",
    )
    rooms: List[RoomDefinition] = Field(
        default_factory=list,
        description="Named rooms for semantic labeling",
    )

    @field_validator("storeys")
    @classmethod
    def validate_storey_order(cls, v: List[StoreyDefinition]) -> List[StoreyDefinition]:
        """Storeys must be listed in ascending elevation order."""
        elevations = [s.elevation for s in v]
        if elevations != sorted(elevations):
            raise ValueError("Storeys must be ordered by ascending elevation")
        return v

    def get_storey(self, storey_ref: str) -> StoreyDefinition:
        """Look up a storey by its ref ID."""
        for s in self.storeys:
            if s.storey_ref == storey_ref:
                return s
        raise ValueError(f"Unknown storey_ref: {storey_ref}")

    def get_wall(self, wall_ref: str) -> WallPlacement:
        """Look up a wall by its ref ID."""
        for e in self.elements:
            if isinstance(e, WallPlacement) and e.wall_ref == wall_ref:
                return e
        raise ValueError(f"Unknown wall_ref: {wall_ref}")

    def walls_on_storey(self, storey_ref: str) -> List[WallPlacement]:
        """Get all walls on a given storey."""
        return [
            e
            for e in self.elements
            if isinstance(e, WallPlacement) and e.storey_ref == storey_ref
        ]

    def openings_for_wall(self, wall_ref: str) -> List[OpeningPlacement]:
        """Get all doors/windows hosted in a given wall."""
        return [
            e
            for e in self.elements
            if isinstance(e, OpeningPlacement) and e.host_wall_ref == wall_ref
        ]


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def _wall_relative_to_global(
    wall: WallPlacement,
    distance_along: float,
    sill_height: float,
    storey_elevation: float,
) -> List[float]:
    """Convert wall-relative position to global [x, y, z]."""
    dx = wall.end_point[0] - wall.start_point[0]
    dy = wall.end_point[1] - wall.start_point[1]
    wall_length = math.sqrt(dx ** 2 + dy ** 2)
    t = distance_along / wall_length

    x = wall.start_point[0] + t * dx
    y = wall.start_point[1] + t * dy
    z = storey_elevation + sill_height

    return [round(x, 4), round(y, 4), round(z, 4)]


def plan_to_tool_calls(plan: BuildingPlan) -> List[Dict[str, Any]]:
    """Convert a BuildingPlan into an ordered list of MCP tool calls."""
    calls: List[Dict[str, Any]] = []

    for element in plan.elements:
        if isinstance(element, WallPlacement):
            storey = plan.get_storey(element.storey_ref)
            z = storey.elevation
            height = element.height or storey.floor_to_floor_height
            thickness = element.thickness or (
                0.2 if element.component_id == "exterior_wall" else 0.15
            )

            calls.append(
                {
                    "tool": "create_two_point_wall",
                    "args": {
                        "start_point": [element.start_point[0], element.start_point[1], z],
                        "end_point": [element.end_point[0], element.end_point[1], z],
                        "thickness": thickness,
                        "height": height,
                        "name": element.wall_ref,
                    },
                    "metadata": {
                        "wall_ref": element.wall_ref,
                        "storey_ref": element.storey_ref,
                    },
                }
            )

    for element in plan.elements:
        if isinstance(element, SlabPlacement):
            storey = plan.get_storey(element.storey_ref)
            calls.append(
                {
                    "tool": "create_slab",
                    "args": {
                        "polyline": element.boundary_points,
                        "depth": element.depth or 0.2,
                        "location": [0, 0, storey.elevation],
                        "name": f"Slab_{element.storey_ref}",
                    },
                }
            )

    for element in plan.elements:
        if isinstance(element, OpeningPlacement):
            wall = plan.get_wall(element.host_wall_ref)
            storey = plan.get_storey(element.storey_ref)
            global_pos = _wall_relative_to_global(
                wall,
                element.distance_along_wall,
                element.sill_height,
                storey.elevation,
            )

            if element.element_type == "door":
                calls.append(
                    {
                        "tool": "create_door",
                        "args": {
                            "dimensions": {
                                "width": element.width or 0.9,
                                "height": element.height or 2.1,
                            },
                            "operation_type": element.operation_type or "SINGLE_SWING_LEFT",
                            "location": global_pos,
                        },
                    }
                )
            elif element.element_type == "window":
                calls.append(
                    {
                        "tool": "create_window",
                        "args": {
                            "dimensions": {
                                "width": element.width or 1.2,
                                "height": element.height or 1.5,
                            },
                            "partition_type": element.partition_type or "SINGLE_PANEL",
                            "location": global_pos,
                        },
                    }
                )

    for element in plan.elements:
        if isinstance(element, RoofPlacement):
            calls.append(
                {
                    "tool": "create_roof",
                    "args": {
                        "polyline": element.boundary_points,
                        "roof_type": element.roof_type,
                        "angle": element.angle,
                        "thickness": element.thickness or 0.3,
                    },
                }
            )
        elif isinstance(element, StairsPlacement):
            lower = plan.get_storey(element.storey_ref)
            upper = plan.get_storey(element.target_storey_ref)
            calls.append(
                {
                    "tool": "create_stairs",
                    "args": {
                        "width": element.width,
                        "height": upper.elevation - lower.elevation,
                        "stairs_type": element.stairs_type,
                    },
                }
            )

    return calls
