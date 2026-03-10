"""Build the two-storey mixed-use building entirely via MCP socket commands.

Uses only the high-level MCP tools registered on the Blender addon socket:
  create_two_point_wall, create_slab, create_roof,
  create_window (wall_guid + create_opening=True),
  create_door, create_opening, fill_opening, create_stairs.

Building spec:
  Origin (0, 0). Footprint 10m x 8m.
  Ground Floor (z=0): café — 4 ext walls, kitchen partition, 3 shopfront windows,
                       1 entrance door, floor slab, staircase block.
  First Floor (z=3): studio — 4 ext walls, 2 bedroom partitions, bathroom walls,
                      6 bedroom windows, floor slab, flat roof.
"""
import json
import socket
import sys
import time

# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def mcp(cmd: str, params: dict = None, timeout: int = 60) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", 9876))
    s.sendall(json.dumps({"type": cmd, "params": params or {}}).encode("utf-8"))
    buf = bytearray()
    s.settimeout(timeout)
    while True:
        try:
            chunk = s.recv(65536)
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


def ok(result: dict, label: str) -> str:
    """Print result summary and return GUID if available."""
    status = result.get("status", "?")
    inner = result.get("result", {})
    # Look for guid in common field names
    guid = (
        inner.get("wall_guid") or inner.get("slab_guid") or inner.get("roof_guid")
        or inner.get("door_guid") or inner.get("window_guid") or inner.get("opening_guid")
        or inner.get("stairs_guid") or inner.get("guid") or ""
    )
    success = inner.get("success", status == "success")
    msg = inner.get("message", "")
    print(f"  {'OK' if success else 'FAIL'}  {label:45s}  guid={guid[:8] if guid else '—'}  {msg[:60]}")
    if not success:
        print(f"       RAW: {json.dumps(result)[:300]}")
    return guid


# ---------------------------------------------------------------------------
# Step 0: Clear scene — load a blank IFC project
# ---------------------------------------------------------------------------
print("\n=== Step 0: Clear scene ===")
# Build a blank IFC4 file on disk with the two storeys already in it,
# then load it through the Bonsai addon. This replaces the previous model cleanly.
import tempfile, pathlib, ifcopenshell, ifcopenshell.api as ifc_api

tmp_path = str(pathlib.Path(tempfile.gettempdir()) / "blank_mixed_use.ifc")
_ifc = ifc_api.run("project.create_file", version="IFC4")
_proj = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcProject", name="Mixed-Use Building")
ifc_api.run("unit.assign_unit", _ifc, length={"is_metric": True, "raw": "METRES"})
_site = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcSite", name="Site")
_bldg = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcBuilding", name="Mixed-Use Building A")
_gf   = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcBuildingStorey", name="Ground Floor")
_l1   = ifc_api.run("root.create_entity", _ifc, ifc_class="IfcBuildingStorey", name="First Floor")
_gf.Elevation = 0.0
_l1.Elevation = 3.0
ifc_api.run("aggregate.assign_object", _ifc, relating_object=_proj, products=[_site])
ifc_api.run("aggregate.assign_object", _ifc, relating_object=_site, products=[_bldg])
ifc_api.run("aggregate.assign_object", _ifc, relating_object=_bldg, products=[_gf, _l1])
_ifc.write(tmp_path)

load_code = f"import bpy\nbpy.ops.bim.load_project(filepath=r'{tmp_path}')\nprint('blank loaded')"
r = mcp("execute_code", {"code": load_code}, timeout=30)
output = r.get("result", {}).get("output", str(r))
print(" ", output.strip().splitlines()[-1] if output.strip() else r)

# Set Ground Floor as default container and patch save_and_load_ifc to preserve it
setup_code = (
    "import bonsai.tool as tool\n"
    "import blender_addon.api.ifc_utils as _ifc_utils\n"
    "ifc = tool.Ifc.get()\n"
    "storeys = ifc.by_type('IfcBuildingStorey')\n"
    "gf = next((s for s in storeys if 'Ground' in (s.Name or '')), storeys[0])\n"
    "props = tool.Spatial.get_spatial_props()\n"
    "props.default_container = gf.id()\n"
    "print('Container set to:', gf.Name)\n"
    "# Monkey-patch save_and_load_ifc to preserve default_container\n"
    "_orig = _ifc_utils.save_and_load_ifc\n"
    "def _save_preserving():\n"
    "    _p = tool.Spatial.get_spatial_props()\n"
    "    _saved = _p.default_container\n"
    "    _orig()\n"
    "    _p.default_container = _saved\n"
    "_ifc_utils.save_and_load_ifc = _save_preserving\n"
    "import blender_addon.api.wall as _w; _w.save_and_load_ifc = _save_preserving\n"
    "import blender_addon.api.slab as _sl; _sl.save_and_load_ifc = _save_preserving\n"
    "import blender_addon.api.window as _wi; _wi.save_and_load_ifc = _save_preserving\n"
    "import blender_addon.api.door as _d; _d.save_and_load_ifc = _save_preserving\n"
    "import blender_addon.api.feature as _f; _f.save_and_load_ifc = _save_preserving\n"
    "import blender_addon.api.roof as _r; _r.save_and_load_ifc = _save_preserving\n"
    "import blender_addon.api.stairs as _st; _st.save_and_load_ifc = _save_preserving\n"
    "print('patch applied')\n"
)
r = mcp("execute_code", {"code": setup_code})
print(" ", r.get("result", {}).get("output", r).strip())

time.sleep(1)

# ---------------------------------------------------------------------------
# Step 1: Check scene is alive
# ---------------------------------------------------------------------------
print("\n=== Step 1: Verify scene ===")
r = mcp("ping")
print(" ", r)

# ---------------------------------------------------------------------------
# Step 2: Ground Floor walls
# All coords: south wall y=0, north wall y=8, west x=0, east x=10. z=0.
# Using create_two_point_wall which auto-calculates length + angle.
# ---------------------------------------------------------------------------
print("\n=== Step 2: Ground Floor walls ===")

W, D, GF, L1, WH = 10.0, 8.0, 0.0, 3.0, 3.0
EXT_T, INT_T = 0.2, 0.15

# South wall (faces street, has windows + door)
r = mcp("create_two_point_wall", {
    "start_point": [0.0, 0.0, GF], "end_point": [W, 0.0, GF],
    "name": "GF_South", "thickness": EXT_T, "height": WH
})
gf_south_guid = ok(r, "GF_South wall")

# East wall
r = mcp("create_two_point_wall", {
    "start_point": [W, 0.0, GF], "end_point": [W, D, GF],
    "name": "GF_East", "thickness": EXT_T, "height": WH
})
ok(r, "GF_East wall")

# North wall
r = mcp("create_two_point_wall", {
    "start_point": [0.0, D, GF], "end_point": [W, D, GF],
    "name": "GF_North", "thickness": EXT_T, "height": WH
})
ok(r, "GF_North wall")

# West wall
r = mcp("create_two_point_wall", {
    "start_point": [0.0, 0.0, GF], "end_point": [0.0, D, GF],
    "name": "GF_West", "thickness": EXT_T, "height": WH
})
ok(r, "GF_West wall")

# Kitchen partition: y=5.0, east-west
r = mcp("create_two_point_wall", {
    "start_point": [0.0, 5.0, GF], "end_point": [W, 5.0, GF],
    "name": "GF_Kitchen_Partition", "thickness": INT_T, "height": WH
})
ok(r, "GF_Kitchen_Partition")

# ---------------------------------------------------------------------------
# Step 3: Ground Floor — 3 shopfront windows in south wall
# Centres at x=2, 5, 8. Width=1.8, height=1.2, sill=1.5 → z = 0+1.5 = 1.5
# Pattern: create_opening in wall → create_window → fill_opening
# ---------------------------------------------------------------------------
print("\n=== Step 3: Ground Floor windows ===")
WIN_W, WIN_H, WIN_SILL = 1.8, 1.2, 1.5
for i, cx in enumerate([2.0, 5.0, 8.0]):
    # 1. Cut opening in south wall
    r = mcp("create_opening", {
        "width": WIN_W, "height": WIN_H, "depth": EXT_T + 0.1,
        "location": [cx, 0.0, GF + WIN_SILL],
        "wall_guid": gf_south_guid,
        "name": f"Opening_GF_Win_{i+1}",
    })
    op_guid = r.get("result", {}).get("opening_guid", "")
    ok(r, f"Opening_GF_Win_{i+1}")
    # 2. Create window
    r = mcp("create_window", {
        "name": f"GF_Shopfront_Win_{i+1}",
        "dimensions": {"width": WIN_W, "height": WIN_H},
        "location": [cx, 0.0, GF + WIN_SILL],
        "partition_type": "SINGLE_PANEL",
    })
    win_guid = r.get("result", {}).get("window_guid", "")
    ok(r, f"GF_Shopfront_Win_{i+1}")
    # 3. Fill opening
    if op_guid and win_guid:
        r = mcp("fill_opening", {"opening_guid": op_guid, "element_guid": win_guid})
        ok(r, f"Fill GF_Win_{i+1}")

# ---------------------------------------------------------------------------
# Step 4: Ground Floor — entrance door, centred x=5, south wall
# Width=1.0, height=2.1, sill=0 → z=0.0
# ---------------------------------------------------------------------------
print("\n=== Step 4: Ground Floor entrance door ===")
# 1. Cut opening in south wall
r = mcp("create_opening", {
    "width": 1.0, "height": 2.1, "depth": EXT_T + 0.1,
    "location": [5.0, 0.0, GF],
    "wall_guid": gf_south_guid,
    "name": "Opening_GF_Door",
})
door_op_guid = r.get("result", {}).get("opening_guid", "")
ok(r, "Opening_GF_Door")
# 2. Create door
r = mcp("create_door", {
    "name": "GF_Entrance_Door",
    "dimensions": {"width": 1.0, "height": 2.1},
    "location": [5.0, 0.0, GF],
    "operation_type": "SINGLE_SWING_LEFT",
})
door_guid = r.get("result", {}).get("door_guid", "")
ok(r, "GF_Entrance_Door")
# 3. Fill
if door_op_guid and door_guid:
    r = mcp("fill_opening", {"opening_guid": door_op_guid, "element_guid": door_guid})
    ok(r, "Fill GF_Door opening")

# ---------------------------------------------------------------------------
# Step 5: Ground Floor slab
# ---------------------------------------------------------------------------
print("\n=== Step 5: Ground Floor slab ===")
r = mcp("create_slab", {
    "name": "GF_Slab",
    "polyline": [[0.0, 0.0], [W, 0.0], [W, D], [0.0, D]],
    "depth": 0.2,
    "location": [0.0, 0.0, GF],
})
ok(r, "GF_Slab")

# Switch active container to First Floor for L1 elements
switch_l1 = (
    "import bonsai.tool as tool\n"
    "ifc = tool.Ifc.get()\n"
    "l1 = next(s for s in ifc.by_type('IfcBuildingStorey') if 'First' in (s.Name or ''))\n"
    "tool.Spatial.get_spatial_props().default_container = l1.id()\n"
    "print('Container:', tool.Root.get_default_container().Name)\n"
)
r = mcp("execute_code", {"code": switch_l1})
print(" ", r.get("result", {}).get("output", r).strip())

# ---------------------------------------------------------------------------
# Step 6: First Floor walls
# ---------------------------------------------------------------------------
print("\n=== Step 6: First Floor walls ===")

r = mcp("create_two_point_wall", {
    "start_point": [0.0, 0.0, L1], "end_point": [W, 0.0, L1],
    "name": "L1_South", "thickness": EXT_T, "height": WH
})
l1_south_guid = ok(r, "L1_South wall")

r = mcp("create_two_point_wall", {
    "start_point": [W, 0.0, L1], "end_point": [W, D, L1],
    "name": "L1_East", "thickness": EXT_T, "height": WH
})
l1_east_guid = ok(r, "L1_East wall")

r = mcp("create_two_point_wall", {
    "start_point": [0.0, D, L1], "end_point": [W, D, L1],
    "name": "L1_North", "thickness": EXT_T, "height": WH
})
l1_north_guid = ok(r, "L1_North wall")

r = mcp("create_two_point_wall", {
    "start_point": [0.0, 0.0, L1], "end_point": [0.0, D, L1],
    "name": "L1_West", "thickness": EXT_T, "height": WH
})
l1_west_guid = ok(r, "L1_West wall")

# Bedroom partitions: N-S at x=3.33 and x=6.67
for tag, bx in [("A", W/3), ("B", 2*W/3)]:
    r = mcp("create_two_point_wall", {
        "start_point": [bx, 0.0, L1], "end_point": [bx, D, L1],
        "name": f"L1_Bed_{tag}_Partition", "thickness": INT_T, "height": WH
    })
    ok(r, f"L1_Bed_{tag}_Partition")

# Bathroom walls: NW corner 2.5m x 2.0m
r = mcp("create_two_point_wall", {
    "start_point": [2.5, D-2.0, L1], "end_point": [2.5, D, L1],
    "name": "L1_Bathroom_E_Wall", "thickness": INT_T, "height": WH
})
ok(r, "L1_Bathroom_E_Wall")

r = mcp("create_two_point_wall", {
    "start_point": [0.0, D-2.0, L1], "end_point": [2.5, D-2.0, L1],
    "name": "L1_Bathroom_S_Wall", "thickness": INT_T, "height": WH
})
ok(r, "L1_Bathroom_S_Wall")

# ---------------------------------------------------------------------------
# Step 7: First Floor — 6 bedroom windows (2 per bedroom)
# BW=1.0, BH=1.1, sill=0.9 → z = L1 + 0.9 = 3.9
# BedA (x:0-3.33): south + west
# BedB (x:3.33-6.67): south + north
# BedC (x:6.67-10): south + east
# ---------------------------------------------------------------------------
print("\n=== Step 7: First Floor bedroom windows ===")
BW, BH, BS = 1.0, 1.1, 0.9
bed_wins = [
    ("L1_BedA_Win_1", l1_south_guid, 1.165,         0.0),   # south
    ("L1_BedA_Win_2", l1_west_guid,  0.0,            2.5),   # west
    ("L1_BedB_Win_1", l1_south_guid, 3.33 + 1.165,  0.0),   # south
    ("L1_BedB_Win_2", l1_north_guid, 3.33 + 1.165,  D),     # north
    ("L1_BedC_Win_1", l1_south_guid, 6.67 + 1.165,  0.0),   # south
    ("L1_BedC_Win_2", l1_east_guid,  W - EXT_T,     2.5),   # east
]
for win_name, wall_guid, wx, wy in bed_wins:
    # 1. Cut opening
    r = mcp("create_opening", {
        "width": BW, "height": BH, "depth": EXT_T + 0.1,
        "location": [wx, wy, L1 + BS],
        "wall_guid": wall_guid,
        "name": f"Opening_{win_name}",
    })
    op_guid = r.get("result", {}).get("opening_guid", "")
    ok(r, f"Opening_{win_name}")
    # 2. Create window
    r = mcp("create_window", {
        "name": win_name,
        "dimensions": {"width": BW, "height": BH},
        "location": [wx, wy, L1 + BS],
        "partition_type": "SINGLE_PANEL",
    })
    win_guid = r.get("result", {}).get("window_guid", "")
    ok(r, win_name)
    # 3. Fill
    if op_guid and win_guid:
        r = mcp("fill_opening", {"opening_guid": op_guid, "element_guid": win_guid})
        ok(r, f"Fill {win_name}")

# ---------------------------------------------------------------------------
# Step 8: First Floor slab
# ---------------------------------------------------------------------------
print("\n=== Step 8: First Floor slab ===")
r = mcp("create_slab", {
    "name": "L1_Slab",
    "polyline": [[0.0, 0.0], [W, 0.0], [W, D], [0.0, D]],
    "depth": 0.2,
    "location": [0.0, 0.0, L1],
})
ok(r, "L1_Slab")

# ---------------------------------------------------------------------------
# Step 9: Flat roof at top of L1 walls (z = L1 + WH = 6.0)
# ---------------------------------------------------------------------------
print("\n=== Step 9: Flat roof ===")
ROOF_Z = L1 + WH
r = mcp("create_roof", {
    "name": "L1_Flat_Roof",
    "polyline": [[0.0, 0.0, ROOF_Z], [W, 0.0, ROOF_Z],
                 [W, D, ROOF_Z], [0.0, D, ROOF_Z]],
    "roof_type": "FLAT",
    "angle": 5.0,
    "thickness": 0.2,
})
ok(r, "L1_Flat_Roof")

# ---------------------------------------------------------------------------
# Step 10: Staircase (NE corner, GF→L1)
# Using create_stairs if available, else a mesh box
# ---------------------------------------------------------------------------
print("\n=== Step 10: Staircase ===")
r = mcp("create_stairs", {
    "name": "GF_Stairs",
    "location": [W - 2.0, D - 2.5, GF],
    "width": 2.0,
    "height": WH,
    "length": 2.5,
    "stairs_type": "STRAIGHT",
})
ok(r, "GF_Stairs")

# ---------------------------------------------------------------------------
# Step 11: Frame view + screenshot
# ---------------------------------------------------------------------------
print("\n=== Step 11: Screenshot ===")
import base64, pathlib

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
mcp("execute_code", {"code": frame_code})
mcp("set_viewport_view", {"view_type": "USER"})

r = mcp("capture_blender_3dviewport_screenshot", {})
img_b64 = r.get("result", {}).get("data", {}).get("image", {}).get("data", "")
if img_b64:
    out = pathlib.Path(r"C:\Users\Harold NG\Documents\IFC-GPT\reports\mixed_use_rebuild.png")
    out.write_bytes(base64.b64decode(img_b64))
    print(f"  Screenshot saved: {out}")
else:
    print("  Screenshot failed:", r.get("result", {}).keys())

print("\n=== Done ===")
