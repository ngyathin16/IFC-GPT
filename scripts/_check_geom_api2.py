"""Check geometry API signatures via ifcopenshell.api.run introspection."""
import ifcopenshell
import ifcopenshell.api

ifc = ifcopenshell.api.run("project.create_file", version="IFC4")
model_ctx = ifcopenshell.api.run("context.add_context", ifc, context_type="Model")
body_ctx = ifcopenshell.api.run(
    "context.add_context", ifc,
    context_type="Model", context_identifier="Body",
    target_view="MODEL_VIEW", parent=model_ctx
)

# Test mesh representation with correct keyword
try:
    verts = [[(0,0,0),(3,0,0),(3,1.5,0),(0,1.5,0),(0,0,3.5),(3,0,3.5),(3,1.5,3.5),(0,1.5,3.5)]]
    faces = [[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]]
    rep = ifcopenshell.api.run(
        "geometry.add_mesh_representation", ifc,
        context=body_ctx, vertices=verts, faces=faces
    )
    print(f"mesh rep OK: {rep.is_a()}, items={len(rep.Items)}")
    print(f"  item type: {rep.Items[0].is_a()}")
except Exception as e:
    print(f"mesh rep FAIL: {e}")

# Test slab representation
try:
    poly = [(0.0,0.0),(3.0,0.0),(3.0,1.5),(0.0,1.5)]
    rep2 = ifcopenshell.api.run(
        "geometry.add_slab_representation", ifc,
        context=body_ctx, polyline=poly, depth=0.3
    )
    print(f"slab rep OK: {rep2.is_a()}, items={len(rep2.Items)}")
    print(f"  item type: {rep2.Items[0].is_a()}")
except Exception as e:
    print(f"slab rep FAIL: {e}")

# Build a stair flight using slab rep as a wedge/ramp
# A stair flight is essentially a sloped slab
# Check if there's an extrusion approach
try:
    import ifcopenshell.util.shape_builder as sb_mod
    print(f"\nShapeBuilder available: {dir(sb_mod)}")
except Exception as e:
    print(f"shape_builder: {e}")

# Check what the IFC4 schema says about IfcStairFlight
try:
    flight = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcStairFlight", name="Test")
    print(f"\nIfcStairFlight attrs: {[a for a in dir(flight) if not a.startswith('_')][:20]}")
except Exception as e:
    print(f"stair flight: {e}")
