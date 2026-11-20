"""View-plane tangent transforms with one undo boundary per completed drag."""

from math import atan2

import bpy
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d,
)
from mathutils import Matrix, Vector
from mathutils.geometry import intersect_line_plane

from .feasibility import active_mode, selected_vertex_handles

_active = None


def capture(context):
    selected = {(point.as_pointer(), side) for point, side in selected_vertex_handles(context)}
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
        point.handle_left, point.handle_right = left, right
        point.handle_left_type, point.handle_right_type = lt, rt
    data.update_tag()


def apply(data, snapshot, matrix, *, rotating):
    for si, pi, anchor, left, right, lt, rt, select_left, select_right in snapshot:
        point = data.splines[si].bezier_points[pi]
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
    bl_label = "Drag Spline Tangents"
    bl_description = "Drag to rotate tangents in the view plane or scale their lengths; Esc cancels"
    bl_options = {"UNDO", "BLOCKING"}

    mode: bpy.props.EnumProperty(items=(("ROTATE", "Rotate", ""), ("SCALE", "Scale", "")))
    axis: bpy.props.EnumProperty(items=tuple((axis, axis.title(), "")
                                           for axis in ("X", "Y", "Z", "VIEW", "UNIFORM")), default="VIEW")

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == "VIEW_3D"
                and context.region_data is not None and _active is None
                and active_mode(context) in {"ROTATE", "SCALE"}
                and bool(selected_vertex_handles(context)))

    def invoke(self, context, event):
        global _active
        self.obj = context.edit_object
        self.data = self.obj.data
        self.snapshot = capture(context)
        self.key = tuple(x.as_pointer() for x in (context.window, context.area, context.region))
        self.center_world = self.obj.matrix_world @ self.snapshot[0][2]
        self.center = location_3d_to_region_2d(context.region, context.region_data, self.center_world)
        if self.center is None or abs(self.obj.matrix_world.determinant()) < 1e-12:
            self.report({"WARNING"}, "Tangents need a visible anchor and nonzero object scale")
            return {"CANCELLED"}
        self.previous_vector = None
        self.angle = 0.0
        self.start_pixel = Vector((event.mouse_region_x, event.mouse_region_y))
        self.changed = False
        self.world = self.obj.matrix_world.to_3x3().copy()
        self.inverse = self.world.inverted()
        self.axis_world = (context.region_data.view_rotation @ Vector((0, 0, 1))
                           if self.axis in {"VIEW", "UNIFORM"}
                           else Vector(tuple(float(axis == self.axis) for axis in "XYZ")))
        end = location_3d_to_region_2d(context.region, context.region_data, self.center_world + self.axis_world)
        self.screen_axis = (end - self.center).normalized() if end is not None else Vector((1, 0))
        self.update(context, event)
        _active = self
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("Drag tangents: release to confirm, Esc or right-click to cancel")
        return {"RUNNING_MODAL"}

    def update(self, context, event):
        offset = Vector((event.mouse_region_x, event.mouse_region_y)) - self.center
        if self.mode == "ROTATE":
            if offset.length < 5:
                return
            pixel = (event.mouse_region_x, event.mouse_region_y)
            origin = region_2d_to_origin_3d(context.region, context.region_data, pixel)
            direction = region_2d_to_vector_3d(context.region, context.region_data, pixel)
            hit = intersect_line_plane(origin, origin + direction, self.center_world, self.axis_world)
            if hit is None or (hit - self.center_world).length < 1e-8:
                return
            current = (hit - self.center_world).normalized()
            if self.previous_vector is None:
                self.previous_vector = current
                return
            self.angle += atan2(self.axis_world.dot(self.previous_vector.cross(current)),
                                self.previous_vector.dot(current))
            self.previous_vector = current
            if abs(self.angle) < 1e-6:
                if self.changed:
                    restore(self.data, self.snapshot)
                self.changed = False
                return
            matrix = self.inverse @ Matrix.Rotation(self.angle, 3, self.axis_world) @ self.world
        else:
            if self.axis in "XYZ":
                delta = Vector((event.mouse_region_x, event.mouse_region_y)) - self.start_pixel
                factor = max(1 + delta.dot(self.screen_axis) / 80, 0.01)
            else:
                # Center control starts at the pivot; use a screen diagonal
                # delta instead of a distance ratio to avoid a first-move jump.
                delta = Vector((event.mouse_region_x, event.mouse_region_y)) - self.start_pixel
                factor = max(1 + (delta.x + delta.y) / 160, 0.01)
            if abs(factor - 1) < 1e-6:
                if self.changed:
                    restore(self.data, self.snapshot)
                self.changed = False
                return
            world_scale = (Matrix.Scale(factor, 3, self.axis_world) if self.axis in "XYZ"
                           else Matrix.Scale(factor, 3))
            matrix = self.inverse @ world_scale @ self.world
        apply(self.data, self.snapshot, matrix, rotating=self.mode == "ROTATE")
        self.changed = True
        context.area.tag_redraw()

    def finish(self, context, *, cancel):
        global _active
        if cancel:
            try:
                restore(self.data, self.snapshot)
            except (ReferenceError, IndexError):
                pass
        _active = None
        if context.area is not None:
            context.area.header_text_set(None)
            context.area.tag_redraw()
        return {"CANCELLED"} if cancel else {"FINISHED"}

    def cancel(self, context):
        self.finish(context, cancel=True)

    def modal(self, context, event):
        if _active is not self:
            return {"CANCELLED"}
        if (context.edit_object != self.obj or context.mode != "EDIT_CURVE"
                or tuple(x.as_pointer() for x in (context.window, context.area, context.region)) != self.key):
            return self.finish(context, cancel=True)
        if event.type in {"ESC", "RIGHTMOUSE", "WINDOW_DEACTIVATE"} or (event.ctrl and event.type == "Z"):
            return self.finish(context, cancel=True)
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            self.update(context, event)
        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self.update(context, event)
            return self.finish(context, cancel=not self.changed)
        return {"RUNNING_MODAL"}


def unregister():
    if _active is not None:
        _active.finish(bpy.context, cancel=True)


CLASSES = (SPLINE_MAKER_OT_tangent_drag,)
