# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""Undoable vertex tangent types in the Spline editing context."""

import bpy

from . import edit_drag, lifecycle, segment_selection
from .feasibility import active_mode, editable_bezier_points
from .vertex_selection import supported_curve


VERTEX_TYPES = (
    ("CORNER", "Corner", "Straight vector tangents", "VECTOR"),
    ("SMOOTH", "Smooth", "Automatic tangents calculated by Blender", "AUTOMATIC"),
    ("BEZIER", "Bézier", "Direction-linked, manually editable tangents", "ALIGNED"),
    ("BEZIER_CORNER", "Bézier Corner", "Independent tangents; keeps the spline connected", "FREE_ALIGN"),
)
SELECTION_FLAGS = ("select_control_point", "select_left_handle", "select_right_handle")
_bindings = []


def editing_active(context):
    return (
        context.area is not None and context.area.type == "VIEW_3D"
        and active_mode(context) is not None and supported_curve(context)
    )


def selected_vertices(context):
    # A selected handle identifies its owner. Type changes always affect both
    # tangents of that vertex, without changing the component selection.
    return [point for point in editable_bezier_points(context)
            if any(getattr(point, flag) for flag in SELECTION_FLAGS)]


class SPLINE_MAKER_OT_vertex_type(bpy.types.Operator):
    bl_idname = "spline_maker.vertex_type"
    bl_label = "Set Spline Vertex Type"
    bl_description = "Change both tangents of selected vertices or handle owners without splitting the spline"
    bl_options = {"REGISTER", "UNDO"}

    vertex_type: bpy.props.EnumProperty(
        name="Vertex Type", items=[item[:3] for item in VERTEX_TYPES],
    )

    @classmethod
    def poll(cls, context):
        return editing_active(context) and bool(selected_vertices(context))

    def execute(self, context):
        points = tuple(point for spline in context.edit_object.data.splines
                       for point in spline.bezier_points)
        selection = [tuple(getattr(point, flag) for flag in SELECTION_FLAGS) for point in points]
        native_type = next(item[3] for item in VERTEX_TYPES if item[0] == self.vertex_type)
        # Let Blender calculate vector/auto handles and align manual tangents.
        # Temporarily select the entire owning vertex so one selected handle
        # cannot leave the vertex with mismatched tangent types.
        try:
            for point, flags in zip(points, selection):
                for flag in SELECTION_FLAGS:
                    setattr(point, flag, not point.hide and any(flags))
            result = bpy.ops.curve.handle_type_set(type=native_type)
        finally:
            for point, flags in zip(points, selection):
                for flag, value in zip(SELECTION_FLAGS, flags):
                    setattr(point, flag, value)
        context.edit_object.data.update_tag()
        context.area.tag_redraw()
        return result


def restorable_handles(context):
    if not editing_active(context) or segment_selection.level(context) != "VERTEX":
        return
    for spline in context.edit_object.data.splines:
        for index, point in enumerate(spline.bezier_points):
            if point.hide or not point.select_control_point:
                continue
            for side, opposite in (("left", "right"), ("right", "left")):
                coordinate = f"handle_{side}"
                if (getattr(point, f"{coordinate}_type") not in {"FREE", "ALIGNED"}
                        or not edit_drag.handle_collapsed(point, coordinate)):
                    continue
                neighbor = edit_drag.handle_neighbor(spline, index, coordinate)
                if neighbor is None:
                    continue
                offset = (neighbor - point.co) / 3
                if not offset.length_squared:
                    offset = point.co - getattr(point, f"handle_{opposite}")
                position = point.co + offset
                if position != point.co:
                    yield point, side, position


class SPLINE_MAKER_OT_restore_handle(bpy.types.Operator):
    bl_idname = "spline_maker.restore_handle"
    bl_label = "Restore Handle"
    bl_description = "Restore a collapsed handle on a connected side of the selected vertex"
    bl_options = {"UNDO", "INTERNAL"}

    side: bpy.props.EnumProperty(items=(("left", "Left", ""), ("right", "Right", "")))

    @classmethod
    def poll(cls, context):
        return not any(lifecycle.active_gestures()) and next(restorable_handles(context), None) is not None

    def execute(self, context):
        restored = False
        for point, side, position in restorable_handles(context):
            if side == self.side:
                edit_drag.set_independent_handle(point, edit_drag.snapshot(point), f"handle_{side}", position)
                restored = True
        if not restored:
            return {"CANCELLED"}
        context.edit_object.data.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


def draw_vertex_types(layout):
    for identifier, label, _, _ in VERTEX_TYPES:
        layout.operator(SPLINE_MAKER_OT_vertex_type.bl_idname, text=label).vertex_type = identifier


def draw_handle_restore(layout, context):
    sides = {side for _, side, _ in restorable_handles(context)}
    if sides:
        layout.separator()
        for side in sorted(sides):
            layout.operator(SPLINE_MAKER_OT_restore_handle.bl_idname,
                            text=f"Restore {side.title()} Handle").side = side


class VIEW3D_MT_spline_maker_vertex_types(bpy.types.Menu):
    bl_label = "Spline Vertex Types"

    def draw(self, context):
        draw_vertex_types(self.layout)
        draw_handle_restore(self.layout, context)


class SPLINE_MAKER_OT_vertex_context_menu(bpy.types.Operator):
    bl_idname = "spline_maker.vertex_context_menu"
    bl_label = "Spline Vertex Types"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return editing_active(context)

    def execute(self, context):
        return bpy.ops.wm.call_menu(name=VIEW3D_MT_spline_maker_vertex_types.__name__)


def register():
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is not None:
        keymap = keyconfig.keymaps.new(name="Curve", space_type="EMPTY", region_type="WINDOW")
        item = keymap.keymap_items.new(
            SPLINE_MAKER_OT_vertex_context_menu.bl_idname, "RIGHTMOUSE", "PRESS", head=True,
        )
        _bindings.append((keymap, item))


def unregister():
    for keymap, item in _bindings:
        keymap.keymap_items.remove(item)
    _bindings.clear()


CLASSES = (SPLINE_MAKER_OT_vertex_type, SPLINE_MAKER_OT_restore_handle, VIEW3D_MT_spline_maker_vertex_types,
           SPLINE_MAKER_OT_vertex_context_menu)
