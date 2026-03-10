"""Debug why create_two_point_wall fails after loading blank IFC."""
import json, socket, tempfile, pathlib, ifcopenshell, ifcopenshell.api as ifc_api

def send(cmd, params=None, timeout=30):
    s = socket.socket(); s.connect(("localhost", 9876))
    s.sendall(json.dumps({"type": cmd, "params": params or {}}).encode())
    buf = bytearray(); s.settimeout(timeout)
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk: break
            buf.extend(chunk)
            try: json.loads(buf.decode()); break
            except: pass
        except: break
    s.close(); return json.loads(buf.decode())

# Step 1: Load blank IFC
tmp_path = str(pathlib.Path(tempfile.gettempdir()) / "blank_mixed_use.ifc")
_ifc = ifc_api.run("project.create_file", version="IFC4")
_proj = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcProject", name="Mixed-Use Building")
ifc_api.run("unit.assign_unit", _ifc, length={"is_metric": True, "raw": "METRES"})
_site = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcSite", name="Site")
_bldg = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcBuilding", name="Mixed-Use Building A")
_gf   = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcBuildingStorey", name="Ground Floor")
_l1   = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcBuildingStorey", name="First Floor")
_gf.Elevation = 0.0; _l1.Elevation = 3.0
ifc_api.run("aggregate.assign_object", _ifc, relating_object=_proj, products=[_site])
ifc_api.run("aggregate.assign_object", _ifc, relating_object=_site, products=[_bldg])
ifc_api.run("aggregate.assign_object", _ifc, relating_object=_bldg, products=[_gf, _l1])
_ifc.write(tmp_path)

load_code = f"import bpy\nbpy.ops.bim.load_project(filepath=r'{tmp_path}')\nprint('loaded')"
r = send("execute_code", {"code": load_code}, timeout=30)
print("Load:", r.get("result", {}).get("output", r).strip().splitlines()[-1])

# Step 2: Set container  
set_code = (
    "import bonsai.tool as tool\n"
    "ifc = tool.Ifc.get()\n"
    "storeys = ifc.by_type('IfcBuildingStorey')\n"
    "gf = next((s for s in storeys if 'Ground' in (s.Name or '')), storeys[0])\n"
    "props = tool.Spatial.get_spatial_props()\n"
    "props.default_container = gf.id()\n"
    "c = tool.Root.get_default_container()\n"
    "print('Container:', c.Name if c else 'NONE')\n"
)
r = send("execute_code", {"code": set_code})
print("Container:", r.get("result", {}).get("output", r).strip())

# Step 3: Try creating one wall and print full response
r = send("create_two_point_wall", {
    "start_point": [0.0, 0.0, 0.0], "end_point": [5.0, 0.0, 0.0],
    "name": "TestWall", "thickness": 0.2, "height": 3.0
})
print("Wall result:", json.dumps(r, indent=2)[:600])
