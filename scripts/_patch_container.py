"""Patch save_and_load_ifc to preserve props.default_container across reloads.

Call this once after loading a blank IFC and setting the storey.
It wraps save_and_load_ifc so the container is restored automatically.
"""
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

patch_code = (
    "import blender_addon.api.ifc_utils as _ifc_utils\n"
    "import bonsai.tool as _tool\n"
    "_orig_save = _ifc_utils.save_and_load_ifc\n"
    "def _patched_save():\n"
    "    props = _tool.Spatial.get_spatial_props()\n"
    "    saved_id = props.default_container\n"
    "    _orig_save()\n"
    "    props.default_container = saved_id\n"
    "_ifc_utils.save_and_load_ifc = _patched_save\n"
    "# Also patch all api modules that imported it directly\n"
    "import blender_addon.api.wall as _wall_mod\n"
    "_wall_mod.save_and_load_ifc = _patched_save\n"
    "import blender_addon.api.slab as _slab_mod\n"
    "_slab_mod.save_and_load_ifc = _patched_save\n"
    "import blender_addon.api.window as _win_mod\n"
    "_win_mod.save_and_load_ifc = _patched_save\n"
    "import blender_addon.api.door as _door_mod\n"
    "_door_mod.save_and_load_ifc = _patched_save\n"
    "import blender_addon.api.feature as _feat_mod\n"
    "_feat_mod.save_and_load_ifc = _patched_save\n"
    "import blender_addon.api.roof as _roof_mod\n"
    "_roof_mod.save_and_load_ifc = _patched_save\n"
    "import blender_addon.api.stairs as _stairs_mod\n"
    "_stairs_mod.save_and_load_ifc = _patched_save\n"
    "print('save_and_load_ifc patched to preserve container')\n"
)
r = send("execute_code", {"code": patch_code})
print(r.get("result", {}).get("output", r).strip())

# Verify it works
check_code = (
    "import bonsai.tool as tool\n"
    "c = tool.Root.get_default_container()\n"
    "print('Container after patch check:', c.Name if c else 'NONE')\n"
)
r = send("execute_code", {"code": check_code})
print(r.get("result", {}).get("output", r).strip())
