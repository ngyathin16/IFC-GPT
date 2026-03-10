"""Debug: Check what IfcRelFillsElement relationships exist in the IFC and why IDS fails."""
import ifcopenshell
from pathlib import Path

ifc = ifcopenshell.open("tests/output/golden_ten_storey.ifc")

# Count fills relationships
fills_rels = ifc.by_type("IfcRelFillsElement")
voids_rels = ifc.by_type("IfcRelVoidsElement")
print(f"IfcRelFillsElement count: {len(fills_rels)}")
print(f"IfcRelVoidsElement count: {len(voids_rels)}")

# Check a door
doors = ifc.by_type("IfcDoor")
print(f"\nTotal IfcDoor: {len(doors)}")
d = doors[0]
print(f"Door: {d.Name}")
fills = getattr(d, "FillsVoids", [])
print(f"  FillsVoids: {fills}")

# Check a window
windows = ifc.by_type("IfcWindow")
print(f"\nTotal IfcWindow: {len(windows)}")
w = windows[0]
print(f"Window: {w.Name}")
fills = getattr(w, "FillsVoids", [])
print(f"  FillsVoids: {fills}")

# Check openings
openings = ifc.by_type("IfcOpeningElement")
print(f"\nTotal IfcOpeningElement: {len(openings)}")
if openings:
    o = openings[0]
    print(f"Opening: {o.Name}")
    has_fillings = getattr(o, "HasFillings", [])
    print(f"  HasFillings: {has_fillings}")
    voids = getattr(o, "VoidsElements", [])
    print(f"  VoidsElements: {voids}")

# Try IDS validation and print failing entity details
from ifctester import ids as ids_module
ids_file = ids_module.open("ids/v0.ids")
ids_file.validate(ifc)

for spec in ids_file.specifications:
    if not spec.status and hasattr(spec, "applicable_entities") and len(spec.applicable_entities) > 0:
        print(f"\nFAILING spec: {spec.name}")
        failing = [e for e in spec.applicable_entities if not e.compliance]
        print(f"  Total failing: {len(failing)}")
        if failing:
            first = failing[0]
            print(f"  First failing entity: {first.element}")
            fills = getattr(first.element, "FillsVoids", [])
            print(f"  FillsVoids: {fills}")
            if fills:
                for f in fills:
                    print(f"    {f} -> opening: {f.RelatingOpeningElement}")
