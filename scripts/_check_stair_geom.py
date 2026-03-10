"""Probe the correct way to build stair flight geometry using ifcopenshell."""
import ifcopenshell
import ifcopenshell.api

ifc = ifcopenshell.api.run("project.create_file", version="IFC4")
ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name="P")
ifcopenshell.api.run("unit.assign_unit", ifc, length={"is_metric": True, "raw": "METRES"})
model_ctx = ifcopenshell.api.run("context.add_context", ifc, context_type="Model")
body_ctx = ifcopenshell.api.run(
    "context.add_context", ifc,
    context_type="Model", context_identifier="Body",
    target_view="MODEL_VIEW", parent=model_ctx,
)

# -----------------------------------------------------------------------
# Approach 1: ShapeBuilder extrusion — stepped stair profile
# -----------------------------------------------------------------------
try:
    from ifcopenshell.util.shape_builder import ShapeBuilder
    builder = ShapeBuilder(ifc)
    print("ShapeBuilder available")

    # Build a stepped L-profile for one stair flight
    # 9 risers, each riser 0.194 m high, tread 0.260 m deep, width 1.5 m
    num_risers = 9
    riser_h = 3.5 / num_risers          # ~0.389 m per riser (one storey / 9)
    tread_d = 0.260
    width = 1.5

    # Stepped profile polyline (2D, in XZ plane)
    pts_2d = [(0.0, 0.0)]
    for i in range(num_risers):
        x0 = i * tread_d
        z0 = i * riser_h
        pts_2d.append((x0, z0 + riser_h))          # riser
        pts_2d.append((x0 + tread_d, z0 + riser_h)) # tread
    pts_2d.append((num_risers * tread_d, 0.0))      # bottom back

    profile = builder.polyline(pts_2d, closed=True)
    extrusion = builder.extrude(profile, magnitude=width, position_x_axis=(0, 1, 0), extrusion_vector=(0, 0, 1))
    # Actually extrude in Y direction for width
    # Let's just test creation works
    rep = ifc.createIfcShapeRepresentation(body_ctx, "Body", "SweptSolid", [extrusion])
    print(f"  ShapeBuilder extrusion OK: {rep.is_a()}")
except Exception as e:
    print(f"ShapeBuilder approach: {e}")

# -----------------------------------------------------------------------
# Approach 2: Mesh representation with stepped vertices
# -----------------------------------------------------------------------
try:
    num_risers = 9
    riser_h = 3.5 / num_risers
    tread_d = 0.260
    w = 1.5

    verts_front = []  # front face vertices (y=0)
    verts_back = []   # back face vertices (y=w)
    for i in range(num_risers + 1):
        verts_front.append((i * tread_d, 0.0, i * riser_h))
        verts_back.append((i * tread_d, w, i * riser_h))
    # bottom corners
    verts_front.append((num_risers * tread_d, 0.0, 0.0))
    verts_back.append((num_risers * tread_d, w, 0.0))

    all_verts = verts_front + verts_back
    n = len(verts_front)  # n points per side

    faces = []
    # Front and back faces (polygons)
    front_face = list(range(n))
    back_face = list(range(n + n - 1, n - 1, -1))
    faces.extend([front_face, back_face])
    # Side quads connecting front to back
    for i in range(n - 1):
        faces.append([i, i + 1, n + i + 1, n + i])

    rep2 = ifcopenshell.api.run(
        "geometry.add_mesh_representation", ifc,
        context=body_ctx,
        vertices=[all_verts],
        faces=[faces],
    )
    print(f"Mesh stair rep OK: {rep2.is_a()}, items={len(rep2.Items)}")
except Exception as e:
    print(f"Mesh approach: {e}")

# -----------------------------------------------------------------------
# Approach 3: Simple slab (box) — visible placeholder
# -----------------------------------------------------------------------
try:
    poly = [(0.0, 0.0), (3.0, 0.0), (3.0, 1.5), (0.0, 1.5)]
    rep3 = ifcopenshell.api.run(
        "geometry.add_slab_representation", ifc,
        context=body_ctx, polyline=poly, depth=3.5,
    )
    print(f"Slab-box stair rep OK: {rep3.is_a()}, items={len(rep3.Items)}")
    print(f"  item type: {rep3.Items[0].is_a()}")
except Exception as e:
    print(f"Slab-box approach: {e}")
