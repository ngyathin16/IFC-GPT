"""Test setting the active storey in Blender so get_default_container() works."""
import json
import socket

def send(cmd, params=None, timeout=30):
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

# Check how Bonsai sets default container
code = (
    "import bpy\n"
    "import bonsai.tool as tool\n"
    "ifc = tool.Ifc.get()\n"
    "# List all storeys\n"
    "storeys = ifc.by_type('IfcBuildingStorey')\n"
    "print('Storeys:', [s.Name for s in storeys])\n"
    "# Check current default container\n"
    "try:\n"
    "    c = tool.Root.get_default_container()\n"
    "    print('Default container:', c.Name if c else None)\n"
    "except Exception as e:\n"
    "    print('get_default_container error:', e)\n"
    "# Try setting active collection to Ground Floor\n"
    "for col in bpy.data.collections:\n"
    "    print('  col:', col.name)\n"
    "# Try to find storey collection and set it active\n"
    "layer_col = bpy.context.view_layer.layer_collection\n"
    "def find_col(lc, name):\n"
    "    if name.lower() in lc.name.lower():\n"
    "        return lc\n"
    "    for child in lc.children:\n"
    "        r = find_col(child, name)\n"
    "        if r: return r\n"
    "    return None\n"
    "gf_lc = find_col(layer_col, 'Ground')\n"
    "print('GF layer col:', gf_lc.name if gf_lc else None)\n"
    "if gf_lc:\n"
    "    bpy.context.view_layer.active_layer_collection = gf_lc\n"
    "    print('Set active layer collection to:', gf_lc.name)\n"
    "# Re-check default container\n"
    "try:\n"
    "    c2 = tool.Root.get_default_container()\n"
    "    print('Default container now:', c2.Name if c2 else None)\n"
    "except Exception as e:\n"
    "    print('still failing:', e)\n"
)
r = send("execute_code", {"code": code})
print(r.get("result", {}).get("output", r))
