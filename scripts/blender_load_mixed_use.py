"""Load golden_mixed_use.ifc into Blender, frame the view, and capture a screenshot."""
import json
import pathlib
import socket
import sys


IFC_PATH = str(
    pathlib.Path(__file__).parent.parent / "tests" / "output" / "golden_mixed_use.ifc"
)
SCREENSHOT_PATH = str(
    pathlib.Path(__file__).parent.parent / "reports" / "golden_mixed_use_blender.png"
)


def send(cmd: str, params: dict = None, timeout: int = 60) -> dict:
    """Send one command to the Blender addon socket and return the parsed response."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", 9876))
    s.sendall(json.dumps({"type": cmd, "params": params or {}}).encode("utf-8"))
    buf = bytearray()
    s.settimeout(timeout)
    while True:
        try:
            chunk = s.recv(8192)
            if not chunk:
                break
            buf.extend(chunk)
            try:
                json.loads(buf.decode("utf-8"))
                break
            except json.JSONDecodeError:
                pass
        except TimeoutError:
            break
    s.close()
    return json.loads(buf.decode("utf-8"))


def main() -> None:
    # 1. Load the IFC file
    load_code = (
        "import bpy\n"
        f"bpy.ops.bim.load_project(filepath=r'{IFC_PATH}')\n"
        "print('IFC loaded')\n"
    )
    r = send("execute_code", {"code": load_code}, timeout=60)
    output = r.get("result", {}).get("output", "")
    print("Load:", output.strip().splitlines()[-1] if output.strip() else r)

    # 2. Frame all objects in the 3-D viewport
    frame_code = (
        "import bpy\n"
        "for area in bpy.context.screen.areas:\n"
        "    if area.type == 'VIEW_3D':\n"
        "        for region in area.regions:\n"
        "            if region.type == 'WINDOW':\n"
        "                with bpy.context.temp_override(area=area, region=region):\n"
        "                    bpy.ops.view3d.view_all()\n"
        "                break\n"
        "        break\n"
        "print('framed')\n"
    )
    r = send("execute_code", {"code": frame_code})
    print("Frame:", r.get("result", {}).get("output", "").strip())

    # 3. Set a nice isometric view (front-right-top)
    r = send("set_viewport_view", {"view": "iso_front_right"})
    print("View:", r)

    # 4. Capture screenshot
    r = send("capture_blender_3dviewport_screenshot", {"output_path": SCREENSHOT_PATH})
    status = r.get("status") or r.get("result", {}).get("status", "")
    print("Screenshot:", status, SCREENSHOT_PATH)


if __name__ == "__main__":
    main()
