"""Capture front, side, and isometric views of the current scene."""
import base64, json, pathlib, socket

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

def screenshot(name, view_type=None):
    if view_type:
        send("set_viewport_view", {"view_type": view_type})
    r = send("capture_blender_3dviewport_screenshot", {})
    b64 = r.get("result", {}).get("data", {}).get("image", {}).get("data", "")
    if b64:
        out = pathlib.Path(rf"C:\Users\Harold NG\Documents\IFC-GPT\reports\{name}.png")
        out.write_bytes(base64.b64decode(b64))
        print(f"  Saved: {out.name}")

# Frame all first
frame = (
    "import bpy\n"
    "for area in bpy.context.screen.areas:\n"
    "    if area.type == 'VIEW_3D':\n"
    "        for region in area.regions:\n"
    "            if region.type == 'WINDOW':\n"
    "                with bpy.context.temp_override(area=area, region=region):\n"
    "                    bpy.ops.view3d.view_all()\n"
    "                break\n"
    "        break\n"
)
send("execute_code", {"code": frame})

screenshot("view_front",    "FRONT")
screenshot("view_right",    "RIGHT")
screenshot("view_top",      "TOP")
screenshot("view_iso_user", "USER")
print("Done")
