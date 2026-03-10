"""Manually invoke ifctester PartOf facet on a single door/window to see why it fails."""
import ifcopenshell
import ifcopenshell.util.element
from ifctester.facet import PartOf

ifc = ifcopenshell.open("tests/output/golden_ten_storey.ifc")

door = ifc.by_type("IfcDoor")[0]
win = ifc.by_type("IfcWindow")[0]

# Simulate the IDS spec: partOf relation="IFCRELVOIDSELEMENT IFCRELFILLSELEMENT"
# with entity name IFCOPENINGELEMENT
facet = PartOf(
    name="IFCOPENINGELEMENT",
    relation="IFCRELVOIDSELEMENT IFCRELFILLSELEMENT",
    cardinality="required",
)

door_result = facet(door)
print(f"Door '{door.Name}': pass={bool(door_result)}  reason={door_result.reason}")

win_result = facet(win)
print(f"Window '{win.Name}': pass={bool(win_result)}  reason={win_result.reason}")

# Also try with IFC class name lowercased to check if that's the issue
facet2 = PartOf(
    name="IFCOPENINGELEMENT",
    relation="IFCRELVOIDSELEMENT IFCRELFILLSELEMENT",
    cardinality="required",
)
print(f"\nWith IFCOPENINGELEMENT:")
r = facet2(door)
print(f"  Door: pass={bool(r)} reason={r.reason}")

# What does get_filled_void return?
opening = ifcopenshell.util.element.get_filled_void(door)
print(f"\nOpening from get_filled_void: {opening}")
if opening:
    print(f"  Opening.is_a(): {opening.is_a()}")
    print(f"  Opening.is_a().upper(): {opening.is_a().upper()}")
    host = ifcopenshell.util.element.get_voided_element(opening)
    print(f"  Host wall: {host}")
    print(f"  Host is_a: {host.is_a() if host else None}")
