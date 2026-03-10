"""Send a scene-reset command to Blender via MCP socket and print result."""
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

# 1. Try the proper Bonsai unload operator first
code = (
    "import bpy\n"
    "try:\n"
    "    bpy.ops.bim.unload_project()\n"
    "    print('bim.unload_project OK')\n"
    "except Exception as e:\n"
    "    print(f'unload_project failed: {e}')\n"
    "# Purge all orphan data blocks\n"
    "bpy.ops.outliner.orphans_purge(do_recursive=True)\n"
    "print('purge done')\n"
)
r = send("execute_code", {"code": code})
print("Reset:", r.get("result", {}).get("output", r))

# 2. Check wall count
r = send("get_ifc_scene_overview")
walls = r.get("result", {}).get("class_counts", {}).get("IfcWall", 0)
print(f"Walls in scene after reset: {walls}")
