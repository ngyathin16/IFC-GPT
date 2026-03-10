"""Rebuild mixed-use building using execute_ifc_code for full context access.

Runs all IFC element creation inside the Blender addon's execute_ifc_code
handler, which has proper access to bonsai tools and handles save_and_load_ifc.
The building is created in logical batches to keep each code block manageable.
"""
import base64
import json
import pathlib
import socket
import tempfile
import time

import ifcopenshell
import ifcopenshell.api as ifc_api

# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
def send(cmd: str, params: dict = None, timeout: int = 120) -> dict:
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


def ifc_code(code: str, label: str = "", timeout: int = 120) -> dict:
    """Run code via execute_ifc_code and print result."""
    r = send("execute_ifc_code", {"code": code}, timeout=timeout)
    result = r.get("result", {})
    if isinstance(result, dict):
        success = result.get("success", r.get("status") == "success")
        msg = result.get("message") or result.get("error") or ""
    else:
        success = r.get("status") == "success"
        msg = str(result)[:80]
    tag = "OK  " if success else "FAIL"
    print(f"  {tag}  {label:50s}  {msg[:70]}")
    if not success:
        print(f"       RAW: {json.dumps(r)[:400]}")
    return result


def exec_code(code: str, label: str = "") -> dict:
    """Run arbitrary Blender Python via execute_code."""
    r = send("execute_code", {"code": code})
    out = r.get("result", {}).get("output", str(r)).strip()
    if label:
        print(f"  {label}: {out.splitlines()[-1] if out else r}")
    return r


# ---------------------------------------------------------------------------
# Step 0 – Load blank IFC with correct spatial hierarchy
# ---------------------------------------------------------------------------
print("\n=== Step 0: Load blank IFC ===")
tmp = pathlib.Path(tempfile.gettempdir()) / "blank_mixed_use.ifc"
_f = ifc_api.run("project.create_file", version="IFC4")
_proj = ifc_api.run("root.create_entity", _f, ifc_class="IfcProject", name="Mixed-Use Building")
ifc_api.run("unit.assign_unit", _f, length={"is_metric": True, "raw": "METRES"})
_ctx = ifc_api.run("context.add_context", _f, context_type="Model")
_body = ifc_api.run("context.add_context", _f, context_type="Model",
                    context_identifier="Body", target_view="MODEL_VIEW", parent=_ctx)
_plan = ifc_api.run("context.add_context", _f, context_type="Plan")
_axis = ifc_api.run("context.add_context", _f, context_type="Plan",
                    context_identifier="Axis", target_view="GRAPH_VIEW", parent=_plan)
_site = ifc_api.run("root.create_entity", _f, ifc_class="IfcSite", name="Site")
_bldg = ifc_api.run("root.create_entity", _f, ifc_class="IfcBuilding", name="Mixed-Use Building A")
_gf = ifc_api.run("root.create_entity", _f, ifc_class="IfcBuildingStorey", name="Ground Floor")
_l1 = ifc_api.run("root.create_entity", _f, ifc_class="IfcBuildingStorey", name="First Floor")
_gf.Elevation = 0.0
_l1.Elevation = 3.0
ifc_api.run("aggregate.assign_object", _f, relating_object=_proj, products=[_site])
ifc_api.run("aggregate.assign_object", _f, relating_object=_site, products=[_bldg])
ifc_api.run("aggregate.assign_object", _f, relating_object=_bldg, products=[_gf, _l1])
_f.write(str(tmp))

r = send("execute_code", {"code": f"import bpy\nbpy.ops.bim.load_project(filepath=r'{tmp}')\nprint('loaded')"})
print(" ", r.get("result", {}).get("output", r).strip().splitlines()[-1])
time.sleep(0.5)

# ---------------------------------------------------------------------------
# Step 1 – Ground Floor: all walls via execute_ifc_code (single batch)
# execute_ifc_code uses blender_addon.api functions which have correct context
# ---------------------------------------------------------------------------
print("\n=== Step 1: Ground Floor walls ===")

GF_WALLS_CODE = """
from blender_addon.api.ifc_utils import get_ifc_file, get_default_container, save_and_load_ifc
import bonsai.tool as tool
import ifcopenshell, ifcopenshell.api

ifc = get_ifc_file()
storeys = ifc.by_type('IfcBuildingStorey')
gf = next(s for s in storeys if 'Ground' in (s.Name or ''))
l1 = next(s for s in storeys if 'First' in (s.Name or ''))

from blender_addon.api.wall import create_two_point_wall
guids = {}

walls = [
    ("GF_South",            [0,0,0],   [10,0,0],  0.20, 3.0),
    ("GF_East",             [10,0,0],  [10,8,0],  0.20, 3.0),
    ("GF_North",            [0,8,0],   [10,8,0],  0.20, 3.0),
    ("GF_West",             [0,0,0],   [0,8,0],   0.20, 3.0),
    ("GF_Kitchen_Partition",[0,5,0],   [10,5,0],  0.15, 3.0),
]

# Set GF as container
props = tool.Spatial.get_spatial_props()
props.default_container = gf.id()

for name, sp, ep, t, h in walls:
    r = create_two_point_wall(start_point=sp, end_point=ep, name=name, thickness=t, height=h)
    guids[name] = r.get('wall_guid','')

print('GF walls done:', list(guids.keys()))
print('GF_SOUTH_GUID=' + guids.get('GF_South',''))
"""
r = ifc_code(GF_WALLS_CODE, "GF walls batch")
# Extract GF_South guid from output
gf_south_guid = ""
raw_out = send("execute_ifc_code", {"code": GF_WALLS_CODE}).get("result", {})
# Re-run to get the guid via a query
time.sleep(0.3)

# Get GF_South guid
GUID_QUERY = """
from blender_addon.api.ifc_utils import get_ifc_file
ifc = get_ifc_file()
walls = {w.Name: w.GlobalId for w in ifc.by_type('IfcWall')}
print(walls)
"""
r2 = send("execute_ifc_code", {"code": GUID_QUERY})
import ast
walls_out = r2.get("result", {}).get("output", "{}")
try:
    # parse the printed dict
    wall_line = [l for l in walls_out.splitlines() if l.strip().startswith("{")]
    wall_guids = ast.literal_eval(wall_line[0]) if wall_line else {}
except Exception:
    wall_guids = {}

gf_south_guid = wall_guids.get("GF_South", "")
print(f"  GF_South guid: {gf_south_guid[:12] if gf_south_guid else 'NOT FOUND'}")
print(f"  Walls found: {list(wall_guids.keys())}")

# ---------------------------------------------------------------------------
# Step 2 – Ground Floor openings + windows + door (single batch per element)
# ---------------------------------------------------------------------------
print("\n=== Step 2: Ground Floor openings, windows, door ===")

W, D, GF, L1z = 10.0, 8.0, 0.0, 3.0
EXT_T = 0.2

GF_OPENINGS_CODE = f"""
from blender_addon.api.ifc_utils import get_ifc_file, save_and_load_ifc
from blender_addon.api.feature import create_opening, fill_opening
from blender_addon.api.window import create_window
from blender_addon.api.door import create_door
import bonsai.tool as tool
import ifcopenshell

ifc = get_ifc_file()
storeys = ifc.by_type('IfcBuildingStorey')
gf = next(s for s in storeys if 'Ground' in (s.Name or ''))
props = tool.Spatial.get_spatial_props()
props.default_container = gf.id()

walls = {{w.Name: w.GlobalId for w in ifc.by_type('IfcWall')}}
south = walls.get('GF_South','')

WIN_W, WIN_H, WIN_SILL = 1.8, 1.2, 1.5
results = []

for i, cx in enumerate([2.0, 5.0, 8.0]):
    op = create_opening(width=WIN_W, height=WIN_H, depth={EXT_T+0.1},
                        location=[cx, 0.0, {GF}+WIN_SILL],
                        wall_guid=south, name=f'Opening_GF_Win_{{i+1}}')
    win = create_window(name=f'GF_Shopfront_Win_{{i+1}}',
                        dimensions={{'width':WIN_W,'height':WIN_H}},
                        location=[cx, 0.0, {GF}+WIN_SILL])
    if op.get('opening_guid') and win.get('window_guid'):
        fill_opening(opening_guid=op['opening_guid'], element_guid=win['window_guid'])
    results.append(f"Win{{i+1}}:op={{op.get('success')}},win={{win.get('success')}}")

# Door
door_op = create_opening(width=1.0, height=2.1, depth={EXT_T+0.1},
                         location=[3.5, 0.0, {GF}],
                         wall_guid=south, name='Opening_GF_Door')
door = create_door(name='GF_Entrance_Door',
                   dimensions={{'width':1.0,'height':2.1}},
                   location=[3.5, 0.0, {GF}],
                   operation_type='SINGLE_SWING_LEFT')
if door_op.get('opening_guid') and door.get('door_guid'):
    fill_opening(opening_guid=door_op['opening_guid'], element_guid=door['door_guid'])
results.append(f"Door:op={{door_op.get('success')}},door={{door.get('success')}}")

print('GF openings:', results)
"""
ifc_code(GF_OPENINGS_CODE, "GF windows + door")

# ---------------------------------------------------------------------------
# Step 3 – Ground Floor slab
# ---------------------------------------------------------------------------
print("\n=== Step 3: Ground Floor slab ===")

GF_SLAB_CODE = f"""
from blender_addon.api.ifc_utils import get_ifc_file, save_and_load_ifc
from blender_addon.api.slab import create_slab
import bonsai.tool as tool

ifc = get_ifc_file()
gf = next(s for s in ifc.by_type('IfcBuildingStorey') if 'Ground' in (s.Name or ''))
tool.Spatial.get_spatial_props().default_container = gf.id()

r = create_slab(name='GF_Floor_Slab',
                polyline=[[0,0],[{W},0],[{W},{D}],[0,{D}]],
                depth=0.2, location=[0,0,{GF}])
print('GF slab:', r.get('success'), r.get('slab_guid','')[:8])
"""
ifc_code(GF_SLAB_CODE, "GF floor slab")

# ---------------------------------------------------------------------------
# Step 4 – First Floor walls
# ---------------------------------------------------------------------------
print("\n=== Step 4: First Floor walls ===")

L1_WALLS_CODE = f"""
from blender_addon.api.ifc_utils import get_ifc_file, save_and_load_ifc
from blender_addon.api.wall import create_two_point_wall
import bonsai.tool as tool

ifc = get_ifc_file()
l1 = next(s for s in ifc.by_type('IfcBuildingStorey') if 'First' in (s.Name or ''))
tool.Spatial.get_spatial_props().default_container = l1.id()

walls_def = [
    ("L1_South",            [0,0,{L1z}],   [10,0,{L1z}],  0.20, 3.0),
    ("L1_East",             [10,0,{L1z}],  [10,8,{L1z}],  0.20, 3.0),
    ("L1_North",            [0,8,{L1z}],   [10,8,{L1z}],  0.20, 3.0),
    ("L1_West",             [0,0,{L1z}],   [0,8,{L1z}],   0.20, 3.0),
    ("L1_Bed_A_Partition",  [3.33,0,{L1z}],[3.33,8,{L1z}],0.15, 3.0),
    ("L1_Bed_B_Partition",  [6.67,0,{L1z}],[6.67,8,{L1z}],0.15, 3.0),
    ("L1_Bath_E_Wall",      [2.5,6,{L1z}], [2.5,8,{L1z}], 0.15, 3.0),
    ("L1_Bath_S_Wall",      [0,6,{L1z}],   [2.5,6,{L1z}], 0.15, 3.0),
]

guids = {{}}
for name, sp, ep, t, h in walls_def:
    r = create_two_point_wall(start_point=sp, end_point=ep, name=name, thickness=t, height=h)
    guids[name] = r.get('wall_guid','')

print('L1 walls done:', list(guids.keys()))
for k,v in guids.items():
    print(f'  {{k}}={{v}}')
"""
ifc_code(L1_WALLS_CODE, "L1 walls batch")

# ---------------------------------------------------------------------------
# Step 5 – First Floor windows
# ---------------------------------------------------------------------------
print("\n=== Step 5: First Floor windows ===")

L1_WINS_CODE = f"""
from blender_addon.api.ifc_utils import get_ifc_file, save_and_load_ifc
from blender_addon.api.feature import create_opening, fill_opening
from blender_addon.api.window import create_window
import bonsai.tool as tool

ifc = get_ifc_file()
l1 = next(s for s in ifc.by_type('IfcBuildingStorey') if 'First' in (s.Name or ''))
tool.Spatial.get_spatial_props().default_container = l1.id()

walls = {{w.Name: w.GlobalId for w in ifc.by_type('IfcWall')}}
south = walls.get('L1_South','')
east  = walls.get('L1_East','')
north = walls.get('L1_North','')
west  = walls.get('L1_West','')

BW, BH, BS = 1.0, 1.1, 0.9
bed_wins = [
    ('L1_BedA_Win_1', south, 1.165,       0.0 ),
    ('L1_BedA_Win_2', west,  0.0,         2.5 ),
    ('L1_BedB_Win_1', south, 3.33+1.165,  0.0 ),
    ('L1_BedB_Win_2', north, 3.33+1.165,  8.0 ),
    ('L1_BedC_Win_1', south, 6.67+1.165,  0.0 ),
    ('L1_BedC_Win_2', east,  10.0-0.2,    2.5 ),
]

results = []
for wname, wall_g, wx, wy in bed_wins:
    op  = create_opening(width=BW, height=BH, depth=0.3,
                         location=[wx, wy, {L1z}+BS],
                         wall_guid=wall_g, name=f'Opening_{{wname}}')
    win = create_window(name=wname,
                        dimensions={{'width':BW,'height':BH}},
                        location=[wx, wy, {L1z}+BS])
    if op.get('opening_guid') and win.get('window_guid'):
        fill_opening(opening_guid=op['opening_guid'], element_guid=win['window_guid'])
    results.append(f'{{wname}}:{{op.get("success")}}/{{win.get("success")}}')

print('L1 windows:', results)
"""
ifc_code(L1_WINS_CODE, "L1 windows batch")

# ---------------------------------------------------------------------------
# Step 6 – First Floor slab
# ---------------------------------------------------------------------------
print("\n=== Step 6: First Floor slab ===")

L1_SLAB_CODE = f"""
from blender_addon.api.ifc_utils import get_ifc_file, save_and_load_ifc
from blender_addon.api.slab import create_slab
import bonsai.tool as tool

ifc = get_ifc_file()
l1 = next(s for s in ifc.by_type('IfcBuildingStorey') if 'First' in (s.Name or ''))
tool.Spatial.get_spatial_props().default_container = l1.id()

r = create_slab(name='L1_Floor_Slab',
                polyline=[[0,0],[{W},0],[{W},{D}],[0,{D}]],
                depth=0.2, location=[0,0,{L1z}])
print('L1 slab:', r.get('success'), r.get('slab_guid','')[:8])
"""
ifc_code(L1_SLAB_CODE, "L1 floor slab")

# ---------------------------------------------------------------------------
# Step 7 – Flat roof at z=6.0
# ---------------------------------------------------------------------------
print("\n=== Step 7: Flat roof ===")

ROOF_Z = L1z + 3.0
ROOF_CODE = f"""
from blender_addon.api.ifc_utils import get_ifc_file, save_and_load_ifc
from blender_addon.api.roof import create_roof
import bonsai.tool as tool

ifc = get_ifc_file()
l1 = next(s for s in ifc.by_type('IfcBuildingStorey') if 'First' in (s.Name or ''))
tool.Spatial.get_spatial_props().default_container = l1.id()

r = create_roof(
    polyline=[[0,0,{ROOF_Z}],[{W},0,{ROOF_Z}],[{W},{D},{ROOF_Z}],[0,{D},{ROOF_Z}]],
    roof_type='FLAT', angle=3.0, thickness=0.2, name='Flat_Roof'
)
print('Roof:', r.get('success'), r.get('roof_guid','')[:8])
"""
ifc_code(ROOF_CODE, "Flat roof")

# ---------------------------------------------------------------------------
# Step 8 – Staircase
# ---------------------------------------------------------------------------
print("\n=== Step 8: Staircase ===")

STAIRS_CODE = f"""
from blender_addon.api.ifc_utils import get_ifc_file, save_and_load_ifc
from blender_addon.api.stairs import create_stairs
import bonsai.tool as tool

ifc = get_ifc_file()
gf = next(s for s in ifc.by_type('IfcBuildingStorey') if 'Ground' in (s.Name or ''))
tool.Spatial.get_spatial_props().default_container = gf.id()

r = create_stairs(
    width=1.5, height=3.0, length=3.0,
    stairs_type='STRAIGHT',
    name='GF_Stairs',
    location=[{W-2.5}, {D-3.5}, {GF}]
)
print('Stairs:', r.get('success'), r.get('stairs_guid','')[:8] if r.get('stairs_guid') else r.get('error',''))
"""
ifc_code(STAIRS_CODE, "Staircase")

# ---------------------------------------------------------------------------
# Step 9 – Verify counts
# ---------------------------------------------------------------------------
print("\n=== Step 9: Verify ===")
r = send("get_ifc_scene_overview")
counts = r.get("result", {}).get("class_counts", {})
print(f"  Walls:   {counts.get('IfcWall', 0)}")
print(f"  Windows: {counts.get('IfcWindow', 0)}")
print(f"  Doors:   {counts.get('IfcDoor', 0)}")
print(f"  Slabs:   {counts.get('IfcSlab', 0)}")
print(f"  Roofs:   {counts.get('IfcRoof', 0)}")
print(f"  Stairs:  {counts.get('IfcStair', 0)}")

# ---------------------------------------------------------------------------
# Step 10 – Frame + screenshot
# ---------------------------------------------------------------------------
print("\n=== Step 10: Screenshot ===")
exec_code(
    "import bpy\n"
    "for area in bpy.context.screen.areas:\n"
    "    if area.type == 'VIEW_3D':\n"
    "        for region in area.regions:\n"
    "            if region.type == 'WINDOW':\n"
    "                with bpy.context.temp_override(area=area, region=region):\n"
    "                    bpy.ops.view3d.view_all()\n"
    "                break\n"
    "        break\n"
    "print('framed')\n",
    "frame"
)
send("set_viewport_view", {"view_type": "USER"})

r = send("capture_blender_3dviewport_screenshot", {})
img_b64 = r.get("result", {}).get("data", {}).get("image", {}).get("data", "")
if img_b64:
    out = pathlib.Path(r"C:\Users\Harold NG\Documents\IFC-GPT\reports\mixed_use_rebuild.png")
    out.write_bytes(base64.b64decode(img_b64))
    print(f"  Saved: {out}")
else:
    print("  Screenshot failed")

print("\n=== Done ===")
