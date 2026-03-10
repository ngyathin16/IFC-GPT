"""Debug save_and_load_ifc failure."""
import json, socket

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

code = (
    "from bonsai.bim.ifc import IfcStore\n"
    "print('IfcStore.path:', IfcStore.path)\n"
    "import bonsai.tool as tool\n"
    "c = tool.Root.get_default_container()\n"
    "print('container:', c.Name if c else None)\n"
    # Try creating a wall inline via ifcopenshell to see if save_and_load_ifc is the culprit
    "import ifcopenshell, ifcopenshell.api\n"
    "ifc = tool.Ifc.get()\n"
    "container = c\n"
    "wall = ifcopenshell.api.run('root.create_entity', ifc, ifc_class='IfcWall', name='DebugWall')\n"
    "ifcopenshell.api.run('spatial.assign_container', ifc, products=[wall], relating_structure=container)\n"
    "print('wall created:', wall.GlobalId)\n"
    "# Now test save_and_load_ifc\n"
    "try:\n"
    "    from blender_addon.api.ifc_utils import save_and_load_ifc\n"
    "    save_and_load_ifc()\n"
    "    print('save_and_load_ifc OK')\n"
    "except Exception as e:\n"
    "    import traceback\n"
    "    print('save_and_load_ifc FAILED:', traceback.format_exc())\n"
)
r = send("execute_code", {"code": code})
print(r.get("result", {}).get("output", r))
