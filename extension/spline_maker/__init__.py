"""Spline Maker extension entry point."""

import bpy

from . import ui


def register():
    for cls in ui.CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_curve_add.append(ui.draw_curve_add_menu)


def unregister():
    bpy.types.VIEW3D_MT_curve_add.remove(ui.draw_curve_add_menu)
    for cls in reversed(ui.CLASSES):
        bpy.utils.unregister_class(cls)
