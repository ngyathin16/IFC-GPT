"""Nuke the current IFC model in-memory and reload a blank one via the addon."""
import json
import socket

def send(cmd, params=None, timeout=60):
    s = socket.socket()
    s.connect(("localhost", 9876))
    s.sendall(json.dumps({"type": cmd, "params": params or {}}).encode())
    buf = bytearray()
    s.settimeout(timeout)
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf.extend(chunk)
            try:
                json.loads(buf.decode())
                break
            except json.JSONDecodeError:
                pass
        except TimeoutError:
            break
    s.close()
    return json.loads(buf.decode())

# Write a blank IFC4 file to disk and load it through the addon
import tempfile, pathlib, ifcopenshell, ifcopenshell.api

tmp = pathlib.Path(tempfile.gettempdir()) / "blank_project.ifc"
ifc = ifcopenshell.api.run("project.create_file", version="IFC4")
project = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name="Mixed-Use Building")
ifcopenshell.api.run("unit.assign_unit", ifc, length={"is_metric": True, "raw": "METRES"})
site = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcSite", name="Site")
building = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBuilding", name="Mixed-Use Building A")
gf = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBuildingStorey", name="Ground Floor")
l1 = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBuildingStorey", name="First Floor")
gf.Elevation = 0.0
l1.Elevation = 3.0
ifcopenshell.api.run("aggregate.assign_object", ifc, relating_object=project, products=[site])
ifcopenshell.api.run("aggregate.assign_object", ifc, relating_object=site, products=[building])
ifcopenshell.api.run("aggregate.assign_object", ifc, relating_object=building, products=[gf, l1])
ifc.write(str(tmp))
print(f"Blank IFC written to {tmp}")

# Load it into Blender via the addon
load_code = f"import bpy\nbpy.ops.bim.load_project(filepath=r'{tmp}')\nprint('loaded blank')\n"
r = send("execute_code", {"code": load_code})
print(r.get("result", {}).get("output", r))

# Verify
r = send("get_ifc_scene_overview")
counts = r.get("result", {}).get("class_counts", {})
print("Walls after reset:", counts.get("IfcWall", 0))
print("Storeys:", r.get("result", {}).get("summary", {}).get("storeys", 0))
