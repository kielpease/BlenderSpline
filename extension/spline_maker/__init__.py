# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""Spline extension entry point."""

import bpy

from . import drawing_probe, ui, feasibility, vertex_selection, vertex_types, tangent_drag, transform_gizmos, edit_drag
from . import segment_selection, region_selection, display, lifecycle, insert_vertex, topology_edit, curve_connections
from . import make_planar, profile


CLASSES = (
    ui.CLASSES + feasibility.CLASSES + vertex_selection.CLASSES + vertex_types.CLASSES
    + tangent_drag.CLASSES + transform_gizmos.CLASSES + edit_drag.CLASSES + segment_selection.CLASSES + region_selection.CLASSES
    + insert_vertex.CLASSES
    + topology_edit.CLASSES
    + curve_connections.CLASSES
    + make_planar.CLASSES
    + profile.CLASSES
    + (drawing_probe.SPLINE_MAKER_OT_exit_draw_tool,)
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    for tool in feasibility.WORKSPACE_TOOLS:
        bpy.utils.register_tool(tool)
    bpy.utils.register_tool(drawing_probe.SplineMakerDrawTool, after={"builtin.primitive_cube_add"})
    drawing_probe.register_exit_shortcut()
    feasibility.register_curve_shortcuts()
    display.register()
    vertex_selection.register()
    vertex_types.register()
    segment_selection.register()
    tangent_drag.register_settings()
    bpy.types.VIEW3D_MT_curve_add.append(ui.draw_curve_add_menu)
    bpy.types.UI_MT_button_context_menu.append(edit_drag.draw_coordinate_context_menu)
    lifecycle.register()


def unregister():
    lifecycle.unregister()
    display.unregister()
    tangent_drag.unregister_settings()
    vertex_types.unregister()
    vertex_selection.unregister()
    segment_selection.unregister()
    drawing_probe.unregister_exit_shortcut()
    bpy.types.UI_MT_button_context_menu.remove(edit_drag.draw_coordinate_context_menu)
    bpy.types.VIEW3D_MT_curve_add.remove(ui.draw_curve_add_menu)
    feasibility.unregister_curve_shortcuts()
    bpy.utils.unregister_tool(drawing_probe.SplineMakerDrawTool)
    for tool in reversed(feasibility.WORKSPACE_TOOLS):
        bpy.utils.unregister_tool(tool)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
