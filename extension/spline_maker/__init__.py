"""Spline Maker extension entry point."""

import bpy

from . import drawing_probe, feasibility, ui, vertex_selection


CLASSES = (
    ui.CLASSES + feasibility.CLASSES + vertex_selection.CLASSES
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
    vertex_selection.register()
    bpy.types.VIEW3D_MT_curve_add.append(ui.draw_curve_add_menu)


def unregister():
    vertex_selection.unregister()
    drawing_probe.stop_active()
    drawing_probe.unregister_exit_shortcut()
    bpy.types.VIEW3D_MT_curve_add.remove(ui.draw_curve_add_menu)
    feasibility.unregister_curve_shortcuts()
    bpy.utils.unregister_tool(drawing_probe.SplineMakerDrawTool)
    for tool in reversed(feasibility.WORKSPACE_TOOLS):
        bpy.utils.unregister_tool(tool)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
