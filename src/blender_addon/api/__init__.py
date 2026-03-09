"""
API package for IFC Bonsai MCP addon.
Provides a registry system for command handlers.
"""

_command_registry = {}

def register_command(command_name, description=None):
    """
    Register a command handler function. This function is a decorator factory.

    Args:
        command_name: The name of the command as it will be called via MCP
        description: Optional description of what the command does
    """
    def decorator(handler_function):
        _command_registry[command_name] = {
            'handler': handler_function,
            'description': description or getattr(handler_function, '__doc__', None) or "No description provided"
        }
        return handler_function
    return decorator

def get_command(command_name):
    """
    Get a command handler by name.

    Args:
        command_name: The name of the command

    Returns:
        The handler function or None if not found
    """
    if command_name in _command_registry:
        return _command_registry[command_name]['handler']
    return None

def get_all_commands():
    """
    Get all registered commands.

    Returns:
        Dictionary of command names to their handlers and descriptions
    """
    return _command_registry

from . import (
    code,
    door,
    feature,
    mesh_ifc,
    mesh_trimesh,
    roof,
    root,
    scene,
    slab,
    stairs,
    style,
    system,
    wall,
    window,
)
from .code import execute_code, execute_ifc_code, ping
from .door import create_door, get_door_operation_types, get_door_properties, update_door
from .feature import (
    create_opening,
    fill_opening,
    get_element_openings,
    get_opening_info,
    get_opening_types,
    remove_filling,
    remove_opening,
)
from .mesh_ifc import create_mesh_ifc, get_mesh_examples, list_ifc_entities
from .mesh_trimesh import create_trimesh_ifc, get_trimesh_examples
from .roof import create_roof, delete_roof, get_roof_types, update_roof
from .root import copy_class, delete_ifc_objects, reassign_class
from .scene import (
    get_blender_object_info,
    get_ifc_scene_overview,
    get_object_info,
    get_scene_info,
    get_selected_objects,
)
from .slab import create_slab, get_slab_properties, update_slab
from .style import (
    apply_style_to_object,
    create_pbr_style,
    create_surface_style,
    list_styles,
    remove_style,
    update_style,
)
from .system import list_commands
from .wall import create_wall, get_wall_properties, update_wall
from .window import create_window, get_window_partition_types, get_window_properties, update_window
