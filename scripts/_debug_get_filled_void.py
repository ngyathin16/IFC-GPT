"""Debug get_filled_void on a door and window from the ten-storey IFC."""
import ifcopenshell
import ifcopenshell.util.element

ifc = ifcopenshell.open("tests/output/golden_ten_storey.ifc")

door = ifc.by_type("IfcDoor")[0]
print(f"Door: {door.Name}")
print(f"  FillsVoids attr: {getattr(door, 'FillsVoids', 'N/A')}")
opening = ifcopenshell.util.element.get_filled_void(door)
print(f"  get_filled_void: {opening}")
if opening:
    host = ifcopenshell.util.element.get_voided_element(opening)
    print(f"  get_voided_element: {host}")

win = ifc.by_type("IfcWindow")[0]
print(f"\nWindow: {win.Name}")
print(f"  FillsVoids attr: {getattr(win, 'FillsVoids', 'N/A')}")
opening_w = ifcopenshell.util.element.get_filled_void(win)
print(f"  get_filled_void: {opening_w}")

# Print the signature of get_filled_void
import inspect
print("\nget_filled_void source:")
print(inspect.getsource(ifcopenshell.util.element.get_filled_void))
