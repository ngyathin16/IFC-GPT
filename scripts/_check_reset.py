"""Check available BIM operators for scene reset."""
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

# List bim operators that contain "project" or "load"
code = (
    "import bpy\n"
    "ops = [op for op in dir(bpy.ops.bim) if 'project' in op.lower() or 'load' in op.lower() or 'new' in op.lower()]\n"
    "print('BIM ops:', ops)\n"
    "# Also check what IFC file is currently open\n"
    "try:\n"
    "    import blender_addon.api.ifc_utils as u\n"
    "    f = u.get_ifc_file()\n"
    "    print('IFC schema:', f.schema, 'path:', getattr(f, 'path', 'n/a'))\n"
    "    print('project name:', f.by_type('IfcProject')[0].Name if f.by_type('IfcProject') else 'none')\n"
    "except Exception as e:\n"
    "    print('ifc_utils error:', e)\n"
)
r = send("execute_code", {"code": code})
print(r.get("result", {}).get("output", r))
