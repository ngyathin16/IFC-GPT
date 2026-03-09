"""Blender addon verification script.

Paste and run this in Blender's Python console (Scripting workspace > Console)
to verify the BlenderMCP addon is installed and registered correctly.
It prints PASS or FAIL for each check and only outputs action items if needed.

Usage (in Blender's Python console):
    exec(open(r"C:\Users\Harold NG\Documents\IFC-GPT\scripts\verify_blender_addon.py").read())
"""

import bpy


def _check(label: str, condition: bool) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition


def verify_blender_addon() -> bool:
    """Run all addon verification checks. Returns True if all pass."""
    print("\n=== BlenderMCP Addon Verification ===")
    results = []

    addon_key = "blender_addon"

    results.append(_check(
        "Addon present in bpy.context.preferences.addons",
        addon_key in bpy.context.preferences.addons,
    ))

    results.append(_check(
        "Operator blendermcp.start_server is registered",
        hasattr(bpy.ops, "blendermcp") and hasattr(bpy.ops.blendermcp, "start_server"),
    ))

    results.append(_check(
        "Panel BLENDERMCP_PT_Panel is registered",
        "BLENDERMCP_PT_Panel" in bpy.types.__dict__,
    ))

    results.append(_check(
        "Scene property blendermcp_port exists",
        hasattr(bpy.types.Scene, "blendermcp_port"),
    ))

    all_passed = all(results)

    if all_passed:
        print("\n✓ All checks passed — addon is installed and active.")
    else:
        print("\n✗ One or more checks failed. To fix:")
        print("  1. Open a TERMINAL (not this Blender console) at the project root.")
        print(r"  2. Run: $env:Path = 'C:\Users\Harold NG\.local\bin;' + $env:Path")
        print(r"  3. Run: uv run python scripts\install.py --create-addon-zip")
        print("  4. In Blender: Edit > Preferences > Add-ons > Install...")
        print("     Select: blender_addon.zip from the project root.")
        print("  5. Enable the 'Blender MCP' addon and re-run this script.")

    return all_passed


verify_blender_addon()
