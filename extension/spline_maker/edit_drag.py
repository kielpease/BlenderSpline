"""Snapshot-based anchor translation and direct tangent placement."""

from math import isfinite

import bpy
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d,
)
from mathutils import Vector

from .feasibility import active_mode, editable_bezier_points, move_origin
from . import edit_snapping
from .drag_navigation import DragNavigation

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


def move_normal(context, axis, direction):
    view_normal = context.region_data.view_rotation @ Vector((0, 0, 1))
    if direction is not None:
        normal = view_normal - direction * view_normal.dot(direction)
        return normal.normalized() if normal.length >= 1e-6 else Vector((0, 0, 0))
    if axis == "VIEW":
        return view_normal
    return Vector(tuple(float(letter not in axis) for letter in "XYZ"))


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


def snap_handle(context, position, anchor, directions, view_normal):
    def screen(world):
        return location_3d_to_region_2d(context.region, context.region_data, world)

    pixel, start = screen(position), screen(anchor)
    if pixel is None or start is None:
        return position
    best_distance = float("inf")
    best = position
    for direction in directions:
        unit = direction.normalized()
        normal = view_normal - unit * view_normal.dot(unit)
        if unit.length_squared < 1e-12 or normal.length_squared < 1e-12:
            continue
        nearest = edit_snapping.nearest_line_pixel(pixel, start, screen(anchor + direction))
        if nearest is None:
            continue
        distance = (nearest - pixel).length_squared
        if distance < best_distance:
            hit = project(context, nearest, anchor, normal.normalized())
            if hit is not None:
                best = anchor + unit * (hit - anchor).dot(unit)
                best_distance = distance
    return best


def handle_neighbor(spline, index, coordinate):
    points = spline.bezier_points
    neighbor = index + (-1 if coordinate == "handle_left" else 1)
    if len(points) < 2 or (not spline.use_cyclic_u and not 0 <= neighbor < len(points)):
        return None
    return points[neighbor % len(points)].co.copy()


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


class SPLINE_MAKER_OT_set_selection_coordinate(bpy.types.Operator):
    bl_idname = "spline_maker.set_selection_coordinate"
    bl_label = "Set Selection Coordinate"
    bl_description = "Set a world coordinate for the selection center"
    bl_options = {"INTERNAL", "UNDO"}

    axis: bpy.props.EnumProperty(items=tuple((axis, axis, "") for axis in "XYZ"))
    value: bpy.props.FloatProperty(name="Coordinate", precision=6)

    @classmethod
    def poll(cls, context):
        from . import tangent_drag, vertex_selection
        return (
            context.area is not None and context.area.type == "VIEW_3D"
            and active_mode(context) is not None and vertex_selection.supported_curve(context)
            and _active is None and tangent_drag._active is None and vertex_selection._gesture is None
            and bool(selected_anchors(context))
        )

    def invoke(self, context, event):
        center = context.edit_object.matrix_world @ move_origin(context)
        self.value = center["XYZ".index(self.axis)]
        return context.window_manager.invoke_props_dialog(self, width=240)

    def draw(self, context):
        self.layout.prop(self, "value", text=f"World {self.axis}")

    def execute(self, context):
        obj = context.edit_object
        world = obj.matrix_world
        if not isfinite(self.value) or abs(world.determinant()) < 1e-12:
            self.report({"WARNING"}, "Enter a finite coordinate on a curve with nonzero scale")
            return {"CANCELLED"}
        points = selected_anchors(context)
        center = world @ (sum((point.co for point in points), Vector()) / len(points))
        index = "XYZ".index(self.axis)
        world_delta = Vector((0, 0, 0))
        world_delta[index] = self.value - center[index]
        if abs(world_delta[index]) < 1e-7:
            return {"CANCELLED"}
        local_delta = world.inverted().to_3x3() @ world_delta
        states = [(point, snapshot(point)) for point in points]
        for point, state in states:
            translate_anchor(point, state, local_delta)
        obj.data.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


class SPLINE_MAKER_OT_move_drag(bpy.types.Operator):
    bl_idname = "spline_maker.move_drag"
    bl_label = "Move Spline Selection"
    bl_description = "Move selected vertices, segments, or complete splines along an axis or plane; Esc cancels"
    bl_options = {"UNDO"}

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
        self.direction = (Vector(tuple(float(axis == self.axis) for axis in "XYZ"))
                          if self.axis in {"X", "Y", "Z"} else None)
        self.normal = move_normal(context, self.axis, self.direction)
        if self.normal.length < 1e-6:
            self.report({"WARNING"}, "This axis faces the view; orbit to move along it")
            return {"CANCELLED"}
        pixel = (event.mouse_region_x, event.mouse_region_y)
        self.start = project(context, pixel, self.origin, self.normal)
        if self.start is None:
            self.report({"WARNING"}, "This move plane is edge-on; orbit to use it")
            return {"CANCELLED"}
        self.changed = False
        self.navigation = DragNavigation(context)
        self.world_delta = self.base_delta = Vector((0, 0, 0))
        from .segment_selection import composite
        self.snap_targets = tuple(
            self.obj.matrix_world @ point.co for point in editable_bezier_points(context)
            if point.as_pointer() not in selected
        ) if (
            len(self.points) == 1 and not composite(context)
        ) else ()
        self.snap_axes = tuple(edit_snapping.alignment_axes(self.axis, self.normal))
        _active = self
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set(
            "Move selection: Shift to align; release to confirm; Esc/right-click to cancel"
            if self.snap_axes and self.snap_targets else "Move selection: release to confirm; Esc/right-click to cancel"
        )
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def update(self, context, event):
        pixel = (event.mouse_region_x, event.mouse_region_y)
        if self.navigation.rebase(context):
            self.base_delta = self.world_delta
            self.normal = move_normal(context, self.axis, self.direction)
            self.snap_axes = tuple(edit_snapping.alignment_axes(self.axis, self.normal))
            self.start = project(context, pixel, self.origin + self.base_delta, self.normal)
            return
        hit = project(context, pixel, self.origin + self.base_delta, self.normal)
        if hit is None:
            return
        if self.start is None:
            self.start = hit
            return
        world_delta = hit - self.start
        if self.direction is not None:
            world_delta = self.direction * world_delta.dot(self.direction)
        world_delta += self.base_delta
        if getattr(event, "shift", False) and self.snap_axes and self.snap_targets:
            position = self.origin + world_delta
            snapped = edit_snapping.vertex_alignment(
                position, self.snap_targets, self.snap_axes,
                lambda world: location_3d_to_region_2d(context.region, context.region_data, world),
            )
            world_delta = snapped - self.origin
        self.world_delta = world_delta
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
        if self.navigation.forward(event):
            return {"PASS_THROUGH"}
        if (event.type in {"ESC", "WINDOW_DEACTIVATE"} or (event.ctrl and event.type == "Z")
                or (event.type == "RIGHTMOUSE" and event.value == "PRESS")):
            return self.finish(context, cancel=True)
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"} | edit_snapping.SHIFT_KEYS:
            self.update(context, event)
        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self.update(context, event)
            return self.finish(context, cancel=not self.changed)
        return {"RUNNING_MODAL"}


def unregister():
    if _active is not None:
        _active.finish(bpy.context, cancel=True)


CLASSES = (SPLINE_MAKER_OT_move_drag, SPLINE_MAKER_OT_set_selection_coordinate)
