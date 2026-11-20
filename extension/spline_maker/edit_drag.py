"""Snapshot-based anchor translation and direct tangent placement."""

import bpy
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
from mathutils import Vector

from .feasibility import active_mode, editable_bezier_points, move_origin

_active = None


def project(context, pixel, origin, normal):
    # Orthographic lines need no far-clip offset. Keep the origin near the
    # view and use the direction directly to avoid losing precision in a
    # distant (start + direction) endpoint.
    start = region_2d_to_origin_3d(context.region, context.region_data, pixel, clamp=0.0)
    direction = region_2d_to_vector_3d(context.region, context.region_data, pixel)
    denominator = direction.dot(normal)
    if abs(denominator) < 1e-7:
        return None
    return start + direction * ((origin - start).dot(normal) / denominator)


def snapshot(point):
    return (point.co.copy(), point.handle_left.copy(), point.handle_right.copy(),
            point.handle_left_type, point.handle_right_type)


def restore(point, state):
    anchor, left, right, lt, rt = state
    point.handle_left_type = point.handle_right_type = "FREE"
    point.co, point.handle_left, point.handle_right = anchor, left, right
    point.handle_left_type, point.handle_right_type = lt, rt


def translate_anchor(point, state, delta):
    anchor, left, right, lt, rt = state
    point.handle_left_type = point.handle_right_type = "FREE"
    point.co, point.handle_left, point.handle_right = anchor + delta, left + delta, right + delta
    point.handle_left_type, point.handle_right_type = lt, rt


def translate_handle(point, state, coordinate, delta):
    anchor, left, right, lt, rt = state
    linked = lt == rt and lt in {"AUTO", "ALIGNED"}
    if coordinate == "handle_left":
        left = left + delta
        if linked and (left - anchor).length > 1e-8:
            right = anchor - (left - anchor).normalized() * (right - anchor).length
    else:
        right = right + delta
        if linked and (right - anchor).length > 1e-8:
            left = anchor - (right - anchor).normalized() * (left - anchor).length
    # Manual edits must persist; AUTO becomes linked, VECTOR becomes Free.
    if linked:
        lt = rt = "ALIGNED"
    elif (lt if coordinate == "handle_left" else rt) in {"AUTO", "VECTOR"}:
        lt = rt = "FREE"
    point.handle_left_type = point.handle_right_type = "FREE"
    point.handle_left, point.handle_right = left, right
    point.handle_left_type, point.handle_right_type = lt, rt


def selected_anchors(context):
    from . import segment_selection
    if segment_selection.level(context) == "WHOLE":
        from .region_selection import whole_selected
        data = context.edit_object.data
        return ([point for spline in data.splines if spline.type == "BEZIER" for point in spline.bezier_points]
                if whole_selected(data) else [])
    if segment_selection.level(context) == "REGION":
        from .region_selection import selected_regions
        data = context.edit_object.data
        return [point for index in sorted(selected_regions(data)) for point in data.splines[index].bezier_points]
    if segment_selection.is_active(context):
        data = context.edit_object.data
        keys = segment_selection.endpoints(data, segment_selection.selected(data))
        return [data.splines[si].bezier_points[pi] for si, pi in sorted(keys)]
    return [point for point in editable_bezier_points(context) if point.select_control_point]


class SPLINE_MAKER_OT_move_drag(bpy.types.Operator):
    bl_idname = "spline_maker.move_drag"
    bl_label = "Move Spline Selection"
    bl_description = "Move selected vertices, segments, or complete splines along an axis or plane; Esc cancels"
    bl_options = {"UNDO", "BLOCKING"}

    axis: bpy.props.EnumProperty(items=tuple((axis, axis, "")
                                           for axis in ("X", "Y", "Z", "XY", "YZ", "XZ", "VIEW")),
                                 default="VIEW")

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == "VIEW_3D"
                and context.region_data is not None and active_mode(context) == "MOVE"
                and _active is None and bool(selected_anchors(context)))

    def invoke(self, context, event):
        global _active
        self.obj, self.data = context.edit_object, context.edit_object.data
        selected = {point.as_pointer() for point in selected_anchors(context)}
        self.points = [(si, pi, snapshot(point))
                       for si, spline in enumerate(self.data.splines) if spline.type == "BEZIER"
                       for pi, point in enumerate(spline.bezier_points) if point.as_pointer() in selected]
        self.region_key = tuple(x.as_pointer() for x in (context.window, context.area, context.region))
        if abs(self.obj.matrix_world.determinant()) < 1e-12:
            return {"CANCELLED"}
        self.inverse = self.obj.matrix_world.inverted().to_3x3()
        self.origin = self.obj.matrix_world @ move_origin(context)
        view_normal = context.region_data.view_rotation @ Vector((0, 0, 1))
        self.direction = None
        if self.axis in {"X", "Y", "Z"}:
            self.direction = Vector(tuple(float(axis == self.axis) for axis in "XYZ"))
            self.normal = view_normal - self.direction * view_normal.dot(self.direction)
            if self.normal.length < 1e-6:
                self.report({"WARNING"}, "This axis faces the view; orbit to move along it")
                return {"CANCELLED"}
            self.normal.normalize()
        elif self.axis == "VIEW":
            self.normal = view_normal
        else:
            self.normal = Vector(tuple(float(axis not in self.axis) for axis in "XYZ"))
        pixel = (event.mouse_region_x, event.mouse_region_y)
        self.start = project(context, pixel, self.origin, self.normal)
        if self.start is None:
            self.report({"WARNING"}, "This move plane is edge-on; orbit to use it")
            return {"CANCELLED"}
        self.changed = False
        _active = self
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("Move selection: release to confirm; Esc/right-click to cancel")
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def update(self, context, event):
        hit = project(context, (event.mouse_region_x, event.mouse_region_y), self.origin, self.normal)
        if hit is None:
            return
        world_delta = hit - self.start
        if self.direction is not None:
            world_delta = self.direction * world_delta.dot(self.direction)
        delta = self.inverse @ world_delta
        self.changed = delta.length > 1e-8
        for si, pi, state in self.points:
            translate_anchor(self.data.splines[si].bezier_points[pi], state, delta)
        self.data.update_tag()
        context.area.tag_redraw()

    def finish(self, context, *, cancel):
        global _active
        if cancel:
            try:
                for si, pi, state in self.points:
                    restore(self.data.splines[si].bezier_points[pi], state)
                self.data.update_tag()
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
        if (context.mode != "EDIT_CURVE" or context.edit_object != self.obj
                or tuple(x.as_pointer() for x in (context.window, context.area, context.region)) != self.region_key):
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


CLASSES = (SPLINE_MAKER_OT_move_drag,)
