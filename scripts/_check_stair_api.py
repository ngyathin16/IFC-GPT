"""Check available stair geometry API in ifcopenshell."""
import ifcopenshell.api
import inspect

# Check if add_stair_representation exists
try:
    import ifcopenshell.api.geometry
    members = dir(ifcopenshell.api.geometry)
    stair_related = [m for m in members if "stair" in m.lower()]
    print("Stair-related geometry API:", stair_related)
except Exception as e:
    print(f"Error: {e}")

# Check what add_mesh_representation signature looks like
try:
    from ifcopenshell.api.geometry import add_mesh_representation
    print("\nadd_mesh_representation sig:", inspect.signature(add_mesh_representation.add_mesh_representation))
except Exception as e:
    print(f"mesh rep: {e}")

# Check add_wall_representation signature
try:
    from ifcopenshell.api.geometry import add_wall_representation
    print("add_wall_representation sig:", inspect.signature(add_wall_representation.add_wall_representation))
except Exception as e:
    print(f"wall rep: {e}")

# Check if there's a way to create extruded area solid directly
try:
    import ifcopenshell
    ifc = ifcopenshell.api.run("project.create_file", version="IFC4")
    model_ctx = ifcopenshell.api.run("context.add_context", ifc, context_type="Model")
    body_ctx = ifcopenshell.api.run(
        "context.add_context", ifc,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=model_ctx
    )
    # Try a simple box extrusion for stair using wall representation
    rep = ifcopenshell.api.run(
        "geometry.add_wall_representation", ifc,
        context=body_ctx, length=3.0, height=3.5, thickness=1.5
    )
    print(f"\nWall rep works: {rep.is_a()}")
    print(f"  Items: {rep.Items}")
    item = rep.Items[0]
    print(f"  Item type: {item.is_a()}")
except Exception as e:
    print(f"wall rep test: {e}")
