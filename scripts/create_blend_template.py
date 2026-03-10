"""Create a pre-configured Blender workspace template for LLM-IFC-Generation.

This script must be run inside Blender's embedded Python interpreter:

    blender --background --python scripts/create_blend_template.py -- --output workspace/llm_ifc_template.blend

The generated .blend file provides a four-area layout optimised for the
LLM-IFC pipeline:
  - 3D Viewport (largest area, top-left) — IFC model preview via Bonsai
  - Properties panel (right column)      — IFC element inspector
  - Text Editor (bottom-left)            — scratch pad for MCP tool calls
  - Info (bottom strip)                  — operator / MCP event log

Usage:
    blender --background --python scripts/create_blend_template.py -- --output <path>

Arguments (after the '--' separator, passed to this script):
    --output PATH   Destination path for the .blend file.
                    Parent directories are created if they do not exist.
                    Default: workspace/llm_ifc_template.blend
    --help          Show this help message and exit.

Notes:
    - Must be executed with Blender's Python (bpy available).
    - The output directory is created automatically.
    - This script does NOT depend on the uv environment; it runs entirely
      inside Blender's embedded interpreter.
"""
from __future__ import annotations

import argparse
import os
import sys


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments passed after the '--' separator."""
    parser = argparse.ArgumentParser(
        prog="create_blend_template.py",
        description=(
            "Generate a pre-configured Blender workspace .blend file for "
            "the LLM-IFC-Generation pipeline."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output",
        default=os.path.join("workspace", "llm_ifc_template.blend"),
        metavar="PATH",
        help="Destination path for the .blend file (default: workspace/llm_ifc_template.blend)",
    )

    # Blender passes its own args before '--'; everything after '--' is ours.
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    return parser.parse_args(argv)


def _setup_workspace(output_path: str) -> None:
    """Configure Blender's screen areas and save the .blend file.

    Layout (approximate proportions):
    ┌──────────────────────────┬──────────┐
    │                          │          │
    │   3D Viewport            │Properties│
    │   (IFC preview)          │(inspector│
    │                          │)         │
    ├──────────────────────────┤          │
    │  Text Editor             │          │
    │  (MCP scratch pad)       │          │
    ├──────────────────────────┴──────────┤
    │  Info (event log)                   │
    └─────────────────────────────────────┘
    """
    import bpy  # type: ignore[import]  # only available inside Blender

    # -----------------------------------------------------------------------
    # Start from a clean state
    # -----------------------------------------------------------------------
    bpy.ops.wm.read_homefile(use_empty=True)

    # Ensure a single window with one screen
    window = bpy.context.window_manager.windows[0]
    screen = window.screen

    # -----------------------------------------------------------------------
    # Remove all areas and recreate the desired layout.
    # bpy.ops.screen.area_split() is the safest cross-version approach.
    # We start with the single default area and split progressively.
    # -----------------------------------------------------------------------
    # The default area after read_homefile(use_empty=True) is an empty area.
    # We configure it as the 3D Viewport first.
    initial_area = screen.areas[0]
    initial_area.type = "VIEW_3D"

    # Override context to the initial area
    with bpy.context.temp_override(window=window, area=initial_area):
        # Split vertically: left=3D Viewport, right=Properties
        bpy.ops.screen.area_split(direction="VERTICAL", factor=0.75)

    properties_area = screen.areas[1]
    properties_area.type = "PROPERTIES"

    viewport_area = screen.areas[0]

    # Split the viewport horizontally: top=3D Viewport, bottom=Text Editor
    with bpy.context.temp_override(window=window, area=viewport_area):
        bpy.ops.screen.area_split(direction="HORIZONTAL", factor=0.70)

    text_area = screen.areas[1]
    text_area.type = "TEXT_EDITOR"

    # Add an info strip at the very bottom by splitting text area
    with bpy.context.temp_override(window=window, area=text_area):
        bpy.ops.screen.area_split(direction="HORIZONTAL", factor=0.85)

    info_area = screen.areas[2] if len(screen.areas) > 2 else None
    if info_area:
        info_area.type = "INFO"

    # -----------------------------------------------------------------------
    # Configure the 3D Viewport for IFC work
    # -----------------------------------------------------------------------
    viewport_area = screen.areas[0]
    for space in viewport_area.spaces:
        if space.type == "VIEW_3D":
            space.shading.type = "SOLID"
            space.shading.color_type = "MATERIAL"
            space.overlay.show_floor = True
            space.overlay.show_axis_x = True
            space.overlay.show_axis_y = True
            break

    # -----------------------------------------------------------------------
    # Pre-populate Text Editor with a usage comment block
    # -----------------------------------------------------------------------
    text_area_space = None
    for area in screen.areas:
        if area.type == "TEXT_EDITOR":
            text_area_space = area.spaces.active
            break

    if text_area_space is not None:
        stub_text = bpy.data.texts.new("mcp_scratch.py")
        stub_text.write(
            "# LLM-IFC-Generation — MCP scratch pad\n"
            "# Run snippets here to call MCP tools directly.\n"
            "#\n"
            "# Example: create a simple wall\n"
            "#   import bpy\n"
            "#   bpy.ops.bim.add_wall()  # or via MCP tool bridge\n"
            "#\n"
            "# See README.md Step 5 for the full agent pipeline.\n"
        )
        text_area_space.text = stub_text

    # -----------------------------------------------------------------------
    # Scene metadata
    # -----------------------------------------------------------------------
    bpy.context.scene.name = "LLM-IFC Workspace"
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "METERS"

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)

    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(output_path))
    print(f"[create_blend_template] Saved workspace to: {os.path.abspath(output_path)}")


def main() -> None:
    """Entry point."""
    args = _parse_args()
    _setup_workspace(args.output)


if __name__ == "__main__":
    main()
