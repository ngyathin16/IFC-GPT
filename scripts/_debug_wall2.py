"""Test: does the container persist after save_and_load_ifc across socket calls?"""
import json, socket, tempfile, pathlib, ifcopenshell, ifcopenshell.api as ifc_api

def send(cmd, params=None, timeout=60):
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

# Check container AFTER previous save_and_load_ifc (from _debug_save.py)
code = (
    "import bonsai.tool as tool\n"
    "c = tool.Root.get_default_container()\n"
    "print('Container after reload:', c.Name if c else 'NONE — RESET!')\n"
    "if not c:\n"
    "    ifc = tool.Ifc.get()\n"
    "    storeys = ifc.by_type('IfcBuildingStorey')\n"
    "    gf = next((s for s in storeys if 'Ground' in (s.Name or '')), storeys[0])\n"
    "    props = tool.Spatial.get_spatial_props()\n"
    "    props.default_container = gf.id()\n"
    "    print('Re-set container to:', gf.Name)\n"
)
r = send("execute_code", {"code": code})
print(r.get("result", {}).get("output", r).strip())

# Now try a wall
r = send("create_two_point_wall", {
    "start_point": [0.0, 0.0, 0.0], "end_point": [5.0, 0.0, 0.0],
    "name": "TestWall2", "thickness": 0.2, "height": 3.0
})
print("Wall:", json.dumps(r.get("result", {}))[:200])
