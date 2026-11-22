"""Insert a native Bézier vertex at a picked point on a visible segment."""

import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d

from . import edit_drag, lifecycle, segment_selection
from .drawing_probe import draw_batch
from .feasibility import active_mode
from .vertex_selection import pointer_in_viewport, supported_curve

_active = None


def closest_parameter(controls, project, pixel, low, high):
    def distance(factor):
        point = segment_selection.split_cubic(controls, factor)[0][-1]
        projected = project(point)
        if projected is None:
            return float("inf")
        return (projected[0] - pixel[0]) ** 2 + (projected[1] - pixel[1]) ** 2

    # Refining the projected cubic also handles straight spans whose parameter
    # is nonlinear in screen space, especially in Perspective view.
    for _ in range(26):
        third = (high - low) / 3
        a, b = low + third, high - third
        if distance(a) <= distance(b):
            high = b
        else:
            low = a
    factor = (low + high) / 2
    return factor, distance(factor)


def pick(data, matrix, project, pixel):
    best, hit = 9 ** 2, None
    for key, start, end in segment_selection.segments(data):
        controls = tuple(matrix @ point for point in (start.co, start.handle_right, end.handle_left, end.co))
        for low, high, a, b in segment_selection.curve_spans(controls, project):
            if segment_selection.distance_squared(pixel, a, b) > 10 ** 2:
                continue
            factor, distance = closest_parameter(controls, project, pixel, low, high)
            if distance < best:
                best = distance
                hit = (key, factor, segment_selection.split_cubic(controls, factor)[0][-1])
    return hit if hit is not None and 0.001 < hit[1] < 0.999 else None


def shortened_endpoint(state, side, shortened, inserted):
    anchor, left, right, left_type, right_type = state
    # Automatic tangents depend on both neighbors. Keep their original
    # evaluated positions when changing one of those neighbors.
    if left_type == right_type == "AUTO":
        left_type = right_type = "ALIGNED"
    else:
        left_type = "FREE" if left_type == "AUTO" else left_type
        right_type = "FREE" if right_type == "AUTO" else right_type
    if side == "right":
        right = shortened
        if right_type == "VECTOR" and (right - anchor.lerp(inserted, 1 / 3)).length > 1e-6:
            right_type = "FREE"
    else:
        left = shortened
        if left_type == "VECTOR" and (left - anchor.lerp(inserted, 1 / 3)).length > 1e-6:
            left_type = "FREE"
    return anchor, left, right, left_type, right_type


def insert(data, key, factor):
    spline_index, start = key
    spline = data.splines[spline_index]
    points = spline.bezier_points
    end = (start + 1) % len(points)
    states = [edit_drag.snapshot(point) for point in points]
    a, b = states[start], states[end]
    left, right = segment_selection.split_cubic((a[0], a[2], b[1], b[0]), factor)
    anchor = left[-1]
    states[start] = shortened_endpoint(a, "right", left[1], anchor)
    states[end] = shortened_endpoint(b, "left", right[2], anchor)
    index = start + 1
    states.insert(index, (anchor, left[2], right[1], "ALIGNED", "ALIGNED"))
    attributes = {
        name: (1 - factor) * getattr(points[start], name) + factor * getattr(points[end], name)
        for name in ("tilt", "radius", "weight_softbody")
    }
    selection = [(point.select_control_point, point.select_left_handle, point.select_right_handle)
                 for path in data.splines for point in path.bezier_points]

    # Native subdivision updates Blender's Edit Mode point indices, including
    # references used by native Undo and animation paths. Supply the clicked
    # parameter after Blender has made room at the right index.
    two_point_loop = spline.use_cyclic_u and len(points) == 2
    for path in data.splines:
        for point in path.bezier_points:
            point.select_control_point = point.select_left_handle = point.select_right_handle = False
    points[start].select_control_point = points[end].select_control_point = True
    result = bpy.ops.curve.subdivide(number_cuts=1)
    if result != {"FINISHED"}:
        for point, flags in zip((p for path in data.splines for p in path.bezier_points), selection):
            point.select_control_point, point.select_left_handle, point.select_right_handle = flags
        return result

    points = spline.bezier_points
    if two_point_loop:
        # Both directed spans share the same endpoints. Remove the extra
        # point inserted on the other span before applying the exact split.
        for point in points:
            point.select_control_point = point.select_left_handle = point.select_right_handle = False
        points[3 if start == 0 else 1].select_control_point = True
        bpy.ops.curve.delete(type="VERT")
        spline = data.splines[spline_index]
        points = spline.bezier_points

    for point, state in zip(points, states):
        edit_drag.restore(point, state)
        point.select_control_point = point.select_left_handle = point.select_right_handle = False
    added = points[index]
    for name, value in attributes.items():
        setattr(added, name, value)
    added.select_control_point = True
    data.splines.active = spline
    data.update_tag()
    return {"FINISHED"}


class SPLINE_MAKER_OT_add_vert(bpy.types.Operator):
    bl_idname = "spline_maker.add_vert"
    bl_label = "Add Vert"
    bl_description = "Click a visible Bézier segment to insert a vertex and preserve its shape"
    bl_options = {"UNDO", "INTERNAL"}

    spline_index: bpy.props.IntProperty(default=-1, options={"HIDDEN", "SKIP_SAVE"})
    segment_index: bpy.props.IntProperty(default=-1, options={"HIDDEN", "SKIP_SAVE"})
    factor: bpy.props.FloatProperty(default=0.5, min=0, max=1, options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        if not (context.area is not None and context.area.type == "VIEW_3D"
                and supported_curve(context) and not any(lifecycle.active_gestures())):
            return False
        if context.edit_object.data.shape_keys:
            cls.poll_message_set("Add Vert requires a curve without shape keys")
            return False
        return True

    def invoke(self, context, event):
        global _active
        if context.region_data is None or context.region.type != "WINDOW":
            return {"CANCELLED"}
        self.viewport = lifecycle.GestureViewport(context)
        self.hit = None
        self.handler = bpy.types.SpaceView3D.draw_handler_add(self.draw_preview, (), "WINDOW", "POST_PIXEL")
        _active = self
        context.window.cursor_modal_set("CROSSHAIR")
        context.area.header_text_set("Add Vert: click a segment; Esc/right-click to cancel")
        context.window_manager.modal_handler_add(self)
        lifecycle.watch()
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def execute(self, context):
        data = context.edit_object.data
        key = (self.spline_index, self.segment_index)
        if (data.shape_keys or not 0.001 < self.factor < 0.999
                or not any(candidate == key for candidate, _, _ in segment_selection.segments(data))):
            return {"CANCELLED"}
        result = insert(data, key, self.factor)
        if result == {"FINISHED"}:
            if active_mode(context) is None:
                bpy.ops.spline_maker.switch_tangent_tool(target="SELECT")
            context.window_manager.spline_maker_selection_level = "VERTEX"
            context.area.tag_redraw()
        return result

    def cancel(self, context):
        global _active
        if _active is self:
            _active = None
            bpy.types.SpaceView3D.draw_handler_remove(self.handler, "WINDOW")
            self.handler = None
            try:
                self.viewport.window.cursor_modal_restore()
            except ReferenceError:
                pass
            self.viewport.redraw(clear_header=True)

    def modal(self, context, event):
        if _active is not self or not self.viewport.matches(context):
            self.cancel(context)
            return {"CANCELLED", "PASS_THROUGH"}
        plain = not (event.alt or event.ctrl or event.shift or event.oskey)
        if (event.type in {"ESC", "WINDOW_DEACTIVATE"} or (event.ctrl and event.type == "Z")
                or (plain and event.type == "RIGHTMOUSE" and event.value == "PRESS")):
            self.cancel(context)
            return {"CANCELLED"}
        clicking = plain and event.type == "LEFTMOUSE" and event.value == "PRESS"
        if not clicking and event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"PASS_THROUGH"}
        pixel = pointer_in_viewport(context, (event.mouse_x, event.mouse_y))
        self.hit = None
        if pixel is not None:
            obj = context.edit_object
            self.hit = pick(obj.data, obj.matrix_world, lambda p: self.project(context, p), pixel)
        context.area.tag_redraw()
        if not clicking or pixel is None:
            return {"PASS_THROUGH"}
        if self.hit is None:
            return {"RUNNING_MODAL"}
        (self.spline_index, self.segment_index), self.factor, _ = self.hit
        self.cancel(context)
        return self.execute(context)

    @staticmethod
    def project(context, world):
        return location_3d_to_region_2d(context.region, context.region_data, world)

    def draw_preview(self):
        context = bpy.context
        if _active is not self or self.hit is None or not self.viewport.matches(context):
            return
        pixel = self.project(context, self.hit[2])
        if pixel is not None:
            x, y = pixel
            corners = ((x - 6, y), (x, y + 6), (x + 6, y), (x, y - 6), (x - 6, y))
            draw_batch(gpu.shader.from_builtin("UNIFORM_COLOR"), "LINE_STRIP", corners, (0.45, 1, 0.78, 1))


CLASSES = (SPLINE_MAKER_OT_add_vert,)
