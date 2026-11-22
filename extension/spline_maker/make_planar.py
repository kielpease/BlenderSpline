# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""Project selected Bézier control geometry onto a common plane."""

from math import isfinite

import bpy
from mathutils import Vector

from . import edit_drag, topology_edit
from .drawing_plane import DRAWING_PLANE_KEY, DRAWING_PLANE_XY


_PLANES = (
    ("DRAWING", "Drawing Plane", "Use the plane recorded when the curve was drawn with Spline", 1),
    ("VIEW", "View Plane", "Use a plane facing the current view through the selection center", 0),
)
_VIEW_ONLY = (_PLANES[1],)
_AUTOMATIC = {"AUTO", "VECTOR"}
_TOLERANCE = 1e-6


def has_drawing_plane(data):
    return data.get(DRAWING_PLANE_KEY) == DRAWING_PLANE_XY


def plane_items(_operator, context):
    obj = context.edit_object if context is not None else None
    return _PLANES if obj is not None and has_drawing_plane(obj.data) else _VIEW_ONLY


def view_normal(context):
    view = context.region_data or context.space_data.region_3d
    return view.view_rotation @ Vector((0, 0, 1)) if view is not None else None


def restore_automatic_types(point, state, types):
    # RNA recalculates tangents when a handle type changes. Keep each native
    # automatic type that still generates the projected control positions.
    for side, kind in zip(("left", "right"), types):
        if kind in _AUTOMATIC:
            attribute = f"handle_{side}_type"
            baseline = edit_drag.snapshot(point)
            setattr(point, attribute, kind)
            if any((actual - wanted).length > _TOLERANCE for actual, wanted in
                   zip((point.handle_left, point.handle_right), state[1:3])):
                edit_drag.restore(point, baseline)


class SPLINE_MAKER_OT_make_planar(bpy.types.Operator):
    bl_idname = "spline_maker.make_planar"
    bl_label = "Make Planar"
    bl_description = "Flatten the selected vertices and their handles onto one plane"
    bl_options = {"UNDO", "INTERNAL"}

    plane: bpy.props.EnumProperty(name="Plane", items=plane_items, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return topology_edit.context_ready(context) and bool(edit_drag.selected_anchors(context))

    def invoke(self, context, event):
        self._view_normal = view_normal(context)
        if not self.properties.is_property_set("plane") and has_drawing_plane(context.edit_object.data):
            self.plane = "DRAWING"
        return context.window_manager.invoke_props_dialog(self, width=280, confirm_text="Make Planar")

    def draw(self, context):
        self.layout.prop(self, "plane", expand=True)

    def execute(self, context):
        obj = context.edit_object
        world = obj.matrix_world.to_3x3()
        try:
            inverse = world.inverted()
        except ValueError:
            self.report({"WARNING"}, "Make Planar requires a curve with nonzero scale")
            return {"CANCELLED"}
        points = edit_drag.selected_anchors(context)
        if self.plane == "DRAWING" and has_drawing_plane(obj.data):
            origin = Vector()
            normal = (inverse.transposed() @ Vector((0, 0, 1))).normalized()
        else:
            origin = sum((point.co for point in points), Vector()) / len(points)
            normal = getattr(self, "_view_normal", None)
            if normal is None:
                normal = view_normal(context)
            if normal is None:
                self.report({"WARNING"}, "Make Planar requires a 3D Viewport for the view plane")
                return {"CANCELLED"}

        # Measure distance along the world-space normal, then apply the
        # displacement in curve coordinates. This also handles skewed objects.
        local_normal = world.transposed() @ normal
        local_direction = inverse @ normal
        plans = []
        changed = False
        for point in points:
            *coordinates, left_type, right_type = edit_drag.snapshot(point)
            distances = [(coordinate - origin).dot(local_normal) for coordinate in coordinates]
            changed |= any(abs(distance) > _TOLERANCE for distance in distances)
            projected = [coordinate - distance * local_direction for coordinate, distance in zip(coordinates, distances)]
            if not all(isfinite(component) for coordinate in projected for component in coordinate):
                self.report({"WARNING"}, "The resulting curve coordinates are out of range")
                return {"CANCELLED"}
            if obj.data.dimensions == "2D" and any(abs(coordinate.z) > _TOLERANCE for coordinate in projected):
                self.report({"WARNING"}, "For this plane, set the curve dimensions to 3D first")
                return {"CANCELLED"}
            if left_type == right_type == "AUTO":
                manual_types = ("ALIGNED", "ALIGNED")
            else:
                manual_types = tuple("FREE" if kind in _AUTOMATIC else kind for kind in (left_type, right_type))
            plans.append((point, (*projected, *manual_types), (left_type, right_type)))

        if not changed:
            self.report({"INFO"}, "The selection is already on this plane")
            return {"CANCELLED"}
        for point, state, _ in plans:
            edit_drag.restore(point, state)
        for point, state, types in plans:
            restore_automatic_types(point, state, types)
        obj.data.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


CLASSES = (SPLINE_MAKER_OT_make_planar,)
