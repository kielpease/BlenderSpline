# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tangent and selection-center transforms with one undo boundary per drag."""

from math import atan2, copysign, degrees, floor, radians

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Matrix, Vector

from .feasibility import active_mode, is_object_mode_key, move_origin, selected_vertex_handles
from .edit_snapping import SHIFT_KEYS
from .drag_navigation import DragNavigation
from . import lifecycle

_active = None
DEFAULT_VERTEX_ROTATION = "GROUP"


def snap_angle(angle):
    magnitude = abs(degrees(angle))
    ten_degree_stop = 10 * floor(magnitude / 10 + 0.5)
    diagonal_stop = 45 * floor(magnitude / 45 + 0.5)
    nearest = min((ten_degree_stop, diagonal_stop), key=lambda stop: abs(stop - magnitude))
    return radians(copysign(nearest, angle))


def snap_scale(factor):
    return max(0.01, floor(factor * 100 + 0.5) / 100)


def transform_readout(mode, amount, *, snapped):
    precision = 0 if snapped else 1
    if mode == "ROTATE":
        return f"Rotate {degrees(amount) + 0.0:.{precision}f}°"
    return f"Scale {amount * 100:.{precision}f}%"


def scale_direction(context, center, center_world, axis, axis_world):
    direction = Vector((1, 1, 0)).normalized() if axis == "XY" else axis_world
    end = location_3d_to_region_2d(context.region, context.region_data, center_world + direction)
    if center is None or end is None:
        return Vector((0, 0))
    return (end - center).normalized()


def uses_selection_center(context, mode):
    from .segment_selection import composite
    return composite(context) or (
        mode == "ROTATE"
        and getattr(context.window_manager, "spline_maker_vertex_rotation", DEFAULT_VERTEX_ROTATION) == "GROUP"
    )


def register_settings():
    bpy.types.WindowManager.spline_maker_vertex_rotation = bpy.props.EnumProperty(
        name="Vertex Rotation",
        items=(
            ("TANGENTS", "Tangents", "Rotate the handles about each selected anchor"),
            ("GROUP", "Group", "Rotate selected anchors and handles about their average position"),
        ),
        default=DEFAULT_VERTEX_ROTATION,
        options={"SKIP_SAVE"},
    )


def unregister_settings():
    for manager in bpy.data.window_managers:
        manager.property_unset("spline_maker_vertex_rotation")
    del bpy.types.WindowManager.spline_maker_vertex_rotation


def has_selection(context):
    from .vertex_selection import supported_curve
    from .segment_selection import composite
    from .edit_drag import selected_anchors
    return supported_curve(context) and bool(selected_anchors(context) if composite(context)
                                              else selected_vertex_handles(context))


def capture(context):
    from .segment_selection import composite
    from .edit_drag import selected_anchors
    selected = ({(point.as_pointer(), side) for point in selected_anchors(context) for side in ("left", "right")}
                if composite(context) else
                {(point.as_pointer(), side) for point, side in selected_vertex_handles(context)})
    return [
        (si, pi, point.co.copy(), point.handle_left.copy(), point.handle_right.copy(),
         point.handle_left_type, point.handle_right_type,
         (point.as_pointer(), "left") in selected, (point.as_pointer(), "right") in selected)
        for si, spline in enumerate(context.edit_object.data.splines) if spline.type == "BEZIER"
        for pi, point in enumerate(spline.bezier_points)
        if (point.as_pointer(), "left") in selected or (point.as_pointer(), "right") in selected
    ]


def restore(data, snapshot):
    for si, pi, anchor, left, right, lt, rt, _, _ in snapshot:
        point = data.splines[si].bezier_points[pi]
        point.handle_left_type = point.handle_right_type = "FREE"
        point.co = anchor
        point.handle_left, point.handle_right = left, right
        point.handle_left_type, point.handle_right_type = lt, rt
    data.update_tag()


def apply(data, snapshot, matrix, *, rotating, pivot=None):
    for si, pi, anchor, left, right, lt, rt, select_left, select_right in snapshot:
        point = data.splines[si].bezier_points[pi]
        if pivot is not None:
            # Geometry transforms retain vertex types, as native curve edits do.
            # Auto/Vector tangents keep their native neighbor-dependent rules.
            point.handle_left_type = point.handle_right_type = "FREE"
            point.co = pivot + matrix @ (anchor - pivot)
            point.handle_left = pivot + matrix @ (left - pivot)
            point.handle_right = pivot + matrix @ (right - pivot)
            point.handle_left_type, point.handle_right_type = lt, rt
            continue
        # Smooth becomes manually linked on first edit. Vector becomes Free.
        target_left = "ALIGNED" if lt == "AUTO" else "FREE" if lt == "VECTOR" else lt
        target_right = "ALIGNED" if rt == "AUTO" else "FREE" if rt == "VECTOR" else rt
        linked = target_left == target_right == "ALIGNED"
        transform_left = select_left or (rotating and linked and select_right)
        transform_right = select_right or (rotating and linked and select_left)
        new_left = anchor + matrix @ (left - anchor) if transform_left else left.copy()
        new_right = anchor + matrix @ (right - anchor) if transform_right else right.copy()
        if linked and not rotating and select_left != select_right:
            # An axis scale may turn the tangent. Keep the other side aligned
            # without changing its length when only one handle is selected.
            if select_left:
                new_right = anchor - (new_left - anchor).normalized() * (right - anchor).length
            else:
                new_left = anchor - (new_right - anchor).normalized() * (left - anchor).length
        point.handle_left_type = point.handle_right_type = "FREE"
        point.handle_left, point.handle_right = new_left, new_right
        point.handle_left_type, point.handle_right_type = target_left, target_right
    data.update_tag()


class SPLINE_MAKER_OT_tangent_drag(bpy.types.Operator):
    bl_idname = "spline_maker.tangent_drag"
    bl_label = "Rotate or Scale Spline Selection"
    bl_description = "Transform vertex tangents, or selected geometry about its center; Esc cancels"
    bl_options = {"UNDO"}

    mode: bpy.props.EnumProperty(items=(("ROTATE", "Rotate", ""), ("SCALE", "Scale", "")))
    axis: bpy.props.EnumProperty(items=tuple((axis, axis if axis == "XY" else axis.title(), "")
                                           for axis in ("X", "Y", "Z", "XY", "VIEW", "UNIFORM")), default="VIEW")

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == "VIEW_3D"
                and context.region_data is not None and not any(lifecycle.active_gestures())
                and active_mode(context) in {"ROTATE", "SCALE"}
                and has_selection(context))

    def invoke(self, context, event):
        global _active
        self.obj = context.edit_object
        self.data = self.obj.data
        self.snapshot = capture(context)
        if not self.snapshot:
            return {"CANCELLED"}
        center = move_origin(context)
        self.pivot = center if uses_selection_center(context, self.mode) else None
        self.key = tuple(x.as_pointer() for x in (context.window, context.area, context.region))
        self.viewport = lifecycle.GestureViewport(context)
        self.center_world = self.obj.matrix_world @ center
        self.center = location_3d_to_region_2d(context.region, context.region_data, self.center_world)
        if self.center is None or abs(self.obj.matrix_world.determinant()) < 1e-12:
            self.report({"WARNING"}, "Transform needs a visible selection center and nonzero object scale")
            return {"CANCELLED"}
        self.previous_vector = None
        self.angle = 0.0
        self.applied_angle = 0.0
        self.factor = self.base_factor = 1.0
        self.navigation = DragNavigation(context)
        self.readout = transform_readout(self.mode, 0.0 if self.mode == "ROTATE" else 1.0,
                                         snapped=getattr(event, "shift", False))
        self.start_pixel = Vector((event.mouse_region_x, event.mouse_region_y))
        self.changed = False
        self.world = self.obj.matrix_world.to_3x3().copy()
        self.inverse = self.world.inverted()
        self.axis_world = (context.region_data.view_rotation @ Vector((0, 0, 1))
                           if self.axis in {"VIEW", "UNIFORM"}
                           else Vector((0, 0, 1)) if self.axis == "XY"
                           else Vector(tuple(float(axis == self.axis) for axis in "XYZ")))
        self.screen_axis = scale_direction(context, self.center, self.center_world, self.axis, self.axis_world)
        if self.mode == "SCALE" and self.axis in {"X", "Y", "Z", "XY"} and not self.screen_axis.length:
            self.report({"WARNING"}, "This scale axis faces the view; orbit or use the center box")
            return {"CANCELLED"}
        if self.mode == "SCALE" and self.axis == "XY" and abs(
                (context.region_data.view_rotation @ Vector((0, 0, 1))).z) < 1e-7:
            self.report({"WARNING"}, "The XY scale plane is edge-on; orbit to use its square")
            return {"CANCELLED"}
        self.update(context, event)
        if self.mode == "ROTATE" and self.previous_vector is None:
            self.report({"WARNING"}, "Rotation plane is edge-on; orbit or use the outer ring")
            return {"CANCELLED"}
        _active = self
        context.window_manager.modal_handler_add(self)
        lifecycle.watch()
        context.area.header_text_set("Rotate/scale selection: release to confirm; Esc/right-click to cancel")
        return {"RUNNING_MODAL"}

    def update(self, context, event):
        pixel = Vector((event.mouse_region_x, event.mouse_region_y))
        rebase = self.navigation.rebase(context)
        if rebase:
            self.center = location_3d_to_region_2d(context.region, context.region_data, self.center_world)
            self.previous_vector = None
            self.angle = self.applied_angle
            self.start_pixel = pixel
            self.base_factor = self.factor
            self.screen_axis = scale_direction(context, self.center, self.center_world, self.axis, self.axis_world)
        if self.center is None:
            return
        snapped = getattr(event, "shift", False)
        if self.mode == "ROTATE":
            if (pixel - self.center).length >= 5:
                from .edit_drag import project
                hit = project(context, pixel, self.center_world, self.axis_world)
                if hit is not None and (hit - self.center_world).length > 1e-8:
                    current = (hit - self.center_world).normalized()
                    if self.previous_vector is not None:
                        self.angle += atan2(self.axis_world.dot(self.previous_vector.cross(current)),
                                            self.previous_vector.dot(current))
                    self.previous_vector = current
            if rebase:
                return
            angle = snap_angle(self.angle) if snapped else self.angle
            self.applied_angle = angle
            self.readout = transform_readout(self.mode, angle, snapped=snapped)
            changed = abs(angle) >= 1e-6
            world_transform = Matrix.Rotation(angle, 3, self.axis_world)
        else:
            if rebase:
                return
            delta = pixel - self.start_pixel
            if self.axis in {"X", "Y", "Z", "XY"}:
                if not self.screen_axis.length:
                    return
                factor = max(self.base_factor + delta.dot(self.screen_axis) / 80, 0.01)
            else:
                # Center control starts at the pivot; use a screen diagonal
                # delta instead of a distance ratio to avoid a first-move jump.
                factor = max(self.base_factor + (delta.x + delta.y) / 160, 0.01)
            if snapped:
                factor = snap_scale(factor)
            self.factor = factor
            self.readout = transform_readout(self.mode, factor, snapped=snapped)
            changed = abs(factor - 1) >= 1e-6
            world_transform = (Matrix.Diagonal((factor, factor, 1)) if self.axis == "XY"
                               else Matrix.Scale(factor, 3, self.axis_world) if self.axis in {"X", "Y", "Z"}
                               else Matrix.Scale(factor, 3))
        if changed:
            matrix = self.inverse @ world_transform @ self.world
            apply(self.data, self.snapshot, matrix, rotating=self.mode == "ROTATE", pivot=self.pivot)
        elif self.changed:
            restore(self.data, self.snapshot)
        self.changed = changed
        context.area.tag_redraw()

    def finish(self, context, *, cancel):
        global _active
        if _active is not self:
            return {"CANCELLED"}
        if cancel:
            try:
                restore(self.data, self.snapshot)
            except (ReferenceError, IndexError):
                pass
        _active = None
        self.viewport.redraw(clear_header=True)
        return {"CANCELLED"} if cancel else {"FINISHED"}

    def cancel(self, context):
        self.finish(context, cancel=True)

    def modal(self, context, event):
        if _active is not self or not self.viewport.matches(context):
            self.finish(context, cancel=True)
            return {"CANCELLED", "PASS_THROUGH"}
        if is_object_mode_key(event) or self.navigation.forward(event):
            return {"PASS_THROUGH"}
        if (event.type in {"ESC", "WINDOW_DEACTIVATE"} or (event.ctrl and event.type == "Z")
                or (event.type == "RIGHTMOUSE" and event.value == "PRESS")):
            return self.finish(context, cancel=True)
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"} | SHIFT_KEYS:
            self.update(context, event)
        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self.update(context, event)
            return self.finish(context, cancel=not self.changed)
        return {"RUNNING_MODAL"}


def unregister():
    if _active is not None:
        _active.finish(bpy.context, cancel=True)


CLASSES = (SPLINE_MAKER_OT_tangent_drag,)
