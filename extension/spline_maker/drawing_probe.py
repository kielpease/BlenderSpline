"""Modal corner placement and viewport preview."""

from math import fsum

import blf
import bpy
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from .drawing_plane import (
    DrawingPlane, DrawingSession, PointPlacement, SplinePoint, project_view_point, segment_preview,
    viewport_grid_spacing,
)


_active = None
_exit_binding = None
_BUTTONS = (("Finish", 84, 160), ("Cancel", 168, 244))
_COMMITTED_COLOR = (0.25, 0.8, 1.0, 1.0)
_PREVIEW_COLOR = (0.45, 1.0, 0.78, 1.0)
_CLOSE_RADIUS = 10


def button_at(pixel):
    if pixel is not None and 45 <= pixel[1] < 71:
        return next((label for label, left, right in _BUTTONS if left <= pixel[0] < right), None)
    return None


def is_finish_press(event):
    return event.type in {"RET", "NUMPAD_ENTER", "RIGHTMOUSE"} and not (
        event.alt or event.ctrl or event.shift or event.oskey
    )


def near_first_vertex(pointer, first_pixel):
    return pointer is not None and first_pixel is not None and (
        (pointer[0] - first_pixel[0]) ** 2 + (pointer[1] - first_pixel[1]) ** 2
        <= _CLOSE_RADIUS ** 2
    )


def commit_curve(context, session, *, closed=False, closing_tangent=None):
    points = session.points
    center = Vector(tuple(fsum(point.anchor[axis] for point in points) / len(points)
                          for axis in range(3)))
    curve = bpy.data.curves.new("Spline", "CURVE")
    curve.dimensions = "3D"
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for index, (point, placed) in enumerate(zip(spline.bezier_points, points)):
        anchor = placed.anchor - center
        point.co = anchor
        tangent = closing_tangent if index == 0 and closing_tangent is not None else placed.tangent
        if tangent is None:
            point.handle_left_type = point.handle_right_type = "VECTOR"
        else:
            point.handle_left_type = point.handle_right_type = "FREE"
            point.handle_left = anchor - tangent
            point.handle_right = anchor + tangent
            point.handle_left_type = point.handle_right_type = "ALIGNED"
    spline.use_cyclic_u = closed

    obj = bpy.data.objects.new(curve.name, curve)
    context.collection.objects.link(obj)
    obj.location = session.plane.to_world(center)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = session.plane.rotation
    for selected in context.selected_objects:
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj


def stop_active():
    if _active is not None:
        _active.cleanup()


class SPLINE_MAKER_OT_draw_spline(bpy.types.Operator):
    bl_idname = "spline_maker.draw_spline"
    bl_label = "Draw Spline"
    bl_description = "Click to place a corner or drag to pull out Bézier handles"
    bl_options = {"UNDO"}

    place_on_invoke: bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and context.area is not None and context.area.type == "VIEW_3D"

    def execute(self, context):
        self.report({"INFO"}, "Start Draw Spline interactively in the 3D Viewport")
        return {"CANCELLED"}

    def invoke(self, context, event):
        global _active
        if _active is not None:
            return {"CANCELLED"}
        if context.region is None or context.region.type != "WINDOW" or context.region_data is None:
            return {"CANCELLED"}

        self.session = DrawingSession(DrawingPlane(
            context.scene.cursor.location, context.region_data.view_rotation,
        ))
        self.target = self.context_key(context)
        self.pointer = None
        self.placement = None
        self.close_pressed = False
        self.shift = event.shift
        if self.place_on_invoke:
            pixel = (event.mouse_x - context.region.x, event.mouse_y - context.region.y)
            self.begin_placement(context, pixel)
            self.pointer = pixel
        self.handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_overlay, (), "WINDOW", "POST_PIXEL"
        )
        _active = self
        context.window.cursor_modal_set("CROSSHAIR")
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    @staticmethod
    def context_key(context):
        return tuple(
            item.as_pointer() if item else None
            for item in (context.window, context.area, context.region, context.scene)
        )

    def cleanup(self):
        global _active
        if _active is self:
            _active = None
            bpy.types.SpaceView3D.draw_handler_remove(self.handler, "WINDOW")
            self.session.cancel()
            for window in bpy.context.window_manager.windows:
                if window.as_pointer() == self.target[0]:
                    window.cursor_modal_restore()
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()

    def cancel(self, context):
        self.cleanup()

    def finish(self, context, *, closed=False, closing_tangent=None):
        minimum_points = 3 if closed else 2
        if len(self.session.points) < minimum_points:
            message = "Place at least three points to close" if closed else "Place at least two points to finish"
            self.report({"INFO"}, message)
            return {"RUNNING_MODAL"}
        try:
            obj = commit_curve(context, self.session, closed=closed, closing_tangent=closing_tangent)
            from .region_selection import select_whole
            select_whole(obj.data, True)
            context.window_manager.spline_maker_selection_level = "WHOLE"
        finally:
            self.cleanup()
        bpy.ops.wm.tool_set_by_id(name="builtin.select_box", space_type="VIEW_3D")
        if context.area is not None:
            context.area.tag_redraw()
        return {"FINISHED"}

    def project(self, context, pixel):
        return project_view_point(
            self.session.plane, context.region, context.region_data, pixel
        )

    def screen_position(self, context, anchor):
        return view3d_utils.location_3d_to_region_2d(
            context.region, context.region_data, self.session.plane.to_world(anchor)
        )

    def over_first_vertex(self, context, pixel):
        return bool(self.session.points) and near_first_vertex(
            pixel, self.screen_position(context, self.session.points[0].anchor)
        )

    def begin_placement(self, context, pixel):
        projected = self.project(context, pixel)
        anchor = placement_anchor(context, self.session, projected, self.shift)
        if self.session.can_place(anchor):
            self.placement = PointPlacement(pixel, anchor, drag_origin=projected)

    def modal(self, context, event):
        if (
            _active is not self or self.context_key(context) != self.target
            or context.mode != "OBJECT" or context.region_data is None
        ):
            self.cleanup()
            return {"CANCELLED"}

        region = context.region
        pixel = (event.mouse_x - region.x, event.mouse_y - region.y)
        inside = 0 <= pixel[0] < region.width and 0 <= pixel[1] < region.height
        for other in context.area.regions:
            if (other.type in {"UI", "TOOLS"} and other.width > 1
                    and other.x <= event.mouse_x < other.x + other.width
                    and other.y <= event.mouse_y < other.y + other.height):
                inside = False
                break
        self.pointer = pixel if inside else None
        self.shift = event.shift
        context.area.tag_redraw()

        moving = event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}
        releasing = event.type == "LEFTMOUSE" and event.value == "RELEASE"
        placement = self.placement
        if placement is not None and inside and (moving or releasing):
            placement.update(pixel, self.project(context, pixel))
        if releasing:
            self.placement = None
            if self.close_pressed:
                self.close_pressed = False
                if placement is not None and placement.point.tangent is not None:
                    return self.finish(context, closed=True, closing_tangent=placement.point.tangent)
                if button_at(self.pointer) is None and self.over_first_vertex(context, self.pointer):
                    return self.finish(context, closed=True)
                return {"RUNNING_MODAL"}
            if placement is not None:
                self.session.place(placement.point.anchor, placement.point.tangent)
                return {"RUNNING_MODAL"}
        elif moving and (placement is not None or self.close_pressed):
            return {"RUNNING_MODAL"}

        if event.value == "PRESS":
            if event.type == "ESC":
                self.cleanup()
                return {"CANCELLED"}
            # Keep the scene undo stack untouched while preview points exist.
            if event.type == "Z" and event.ctrl and not (event.alt or event.oskey):
                if not event.shift:
                    if self.placement is not None or self.close_pressed:
                        self.placement = None
                        self.close_pressed = False
                    else:
                        self.session.undo_point()
                return {"RUNNING_MODAL"}
            if not inside:
                return {"PASS_THROUGH"}
            # Modified right-clicks must reach Blender, including Industry
            # Compatible's Alt+RMB viewport zoom.
            if is_finish_press(event):
                return self.finish(context) if self.placement is None and not self.close_pressed else {"RUNNING_MODAL"}
            if event.type == "BACK_SPACE":
                if self.close_pressed:
                    self.placement = None
                self.close_pressed = False
                self.session.undo_point()
                return {"RUNNING_MODAL"}
            if event.type == "LEFTMOUSE" and not (event.alt or event.ctrl or event.oskey):
                button = button_at(pixel)
                if button == "Finish":
                    return self.finish(context)
                if button == "Cancel":
                    self.cleanup()
                    return {"CANCELLED"}
                if self.over_first_vertex(context, pixel):
                    self.close_pressed = True
                    if len(self.session.points) >= 3:
                        projected = self.project(context, pixel)
                        if projected is not None:
                            self.placement = PointPlacement(
                                pixel, self.session.points[0].anchor, drag_origin=projected
                            )
                else:
                    self.begin_placement(context, pixel)
                return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

    def draw_overlay(self):
        context = bpy.context
        if (
            _active is not self or self.context_key(context) != self.target
            or context.region_data is None
        ):
            return
        points = self.session.points
        button = button_at(self.pointer)
        preview = self.placement.point if self.placement is not None else None
        close_target = self.close_pressed or (
            preview is None and button is None and self.over_first_vertex(context, self.pointer)
        )
        turning_close_handle = self.close_pressed and preview is not None and preview.tangent is not None
        unavailable = False
        if close_target and len(points) >= 3 and not turning_close_handle:
            preview = points[0]
        elif preview is None and self.pointer is not None and button is None and not close_target:
            projected = self.project(context, self.pointer)
            unavailable = projected is None
            anchor = placement_anchor(context, self.session, projected, self.shift)
            if self.session.can_place(anchor):
                preview = SplinePoint(anchor)

        def project(point):
            return self.screen_position(context, point)

        screen = [
            project(point.anchor) for point in points
        ]
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        segments = []
        outgoing = [preview, *points[1:]] if turning_close_handle else points
        for start, end in zip(outgoing, points[1:]):
            segments.extend(visible_lines(project(p) for p in segment_preview(start, end)))
        draw_batch(shader, "LINES", segments, _COMMITTED_COLOR)
        markers = [
            xy for p in screen if p is not None
            for xy in ((p.x - 4, p.y), (p.x + 4, p.y), (p.x, p.y - 4), (p.x, p.y + 4))
        ]
        draw_batch(shader, "LINES", markers, _COMMITTED_COLOR)

        if preview is not None:
            if points:
                segment = segment_preview(points[-1], preview)
                draw_batch(shader, "LINES", visible_lines(project(p) for p in segment), _PREVIEW_COLOR)
            if self.placement is not None and preview.tangent is not None:
                guides = (preview.anchor - preview.tangent, preview.anchor, preview.anchor + preview.tangent)
                draw_batch(shader, "LINES", visible_lines(project(p) for p in guides), _PREVIEW_COLOR)
            pixel = project(preview.anchor)
            if pixel is not None:
                x, y = pixel
                diamond = [(x, y + 5), (x + 5, y), (x, y - 5), (x - 5, y), (x, y + 5)]
                draw_batch(shader, "LINES", visible_lines(diamond), _PREVIEW_COLOR)

        for label, left, right in _BUTTONS:
            draw_batch(shader, "TRI_FAN", [(left, 45), (right, 45), (right, 71), (left, 71)],
                       (0.1, 0.15, 0.22, 1.0))
            draw_text(left + 11, 53, label)
        count = len(self.session.points)
        if count == 0:
            status = "Click for corner or drag handles   |   Shift snaps to grid"
        elif count == 1:
            status = f"{count} / 2 points needed to finish   |   Click for corner or drag handles"
        else:
            status = f"{count} points   |   Click or drag   |   Shift snaps 45°   |   Right-click to finish"
        if turning_close_handle:
            status = "Release to close with Bézier handles"
        elif close_target:
            status = ("Click to close   |   Drag for Bézier handles"
                      if count >= 3 else "Place at least three points to close")
        elif unavailable:
            status = "Placement unavailable. Orbit to face the drawing plane."
        draw_text(84, 81, status)


def placement_anchor(context, session, projected, shift):
    spacing = viewport_grid_spacing(context, session.plane) if (
        shift and projected is not None and not session.points
    ) else 0.0
    return session.placement_anchor(projected, snap=shift, grid_spacing=spacing)


def visible_lines(projected):
    points = list(projected)
    return [p for a, b in zip(points, points[1:]) if a is not None and b is not None for p in (a, b)]


def draw_batch(shader, kind, coordinates, color):
    if coordinates:
        shader.bind()
        shader.uniform_float("color", color)
        batch_for_shader(shader, kind, {"pos": coordinates}).draw(shader)


def draw_text(x, y, text):
    blf.position(0, x, y, 0)
    blf.size(0, 13)
    blf.color(0, 1, 1, 1, 1)
    blf.draw(0, text)


class SPLINE_MAKER_OT_exit_draw_tool(bpy.types.Operator):
    bl_idname = "spline_maker.exit_draw_tool"
    bl_label = "Exit Draw Spline"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        if (
            _active is not None or context.mode != "OBJECT"
            or context.area is None or context.area.type != "VIEW_3D"
        ):
            return False
        tool = context.workspace.tools.from_space_view3d_mode("OBJECT", create=False)
        return tool is not None and tool.idname == SplineMakerDrawTool.bl_idname

    def execute(self, context):
        return bpy.ops.wm.tool_set_by_id(name="builtin.select_box", space_type="VIEW_3D")


class SplineMakerDrawTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = "spline_maker.draw_probe"
    bl_label = "Draw Spline"
    bl_description = "Click in the viewport to place the first spline point"
    bl_icon = "ops.curve.pen"
    bl_cursor = "CROSSHAIR"
    bl_keymap = (
        ("spline_maker.draw_spline", {"type": "LEFTMOUSE", "value": "PRESS"},
         {"properties": [("place_on_invoke", True)]}),
        ("spline_maker.draw_spline", {"type": "LEFTMOUSE", "value": "PRESS", "shift": True},
         {"properties": [("place_on_invoke", True)]}),
    )


def register_exit_shortcut():
    global _exit_binding
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is not None:
        # Object Mode handles its context menu before the active tool keymap.
        keymap = keyconfig.keymaps.new(name="Object Mode", space_type="EMPTY", region_type="WINDOW")
        item = keymap.keymap_items.new(
            SPLINE_MAKER_OT_exit_draw_tool.bl_idname, "RIGHTMOUSE", "PRESS", head=True,
        )
        _exit_binding = keymap, item


def unregister_exit_shortcut():
    global _exit_binding
    if _exit_binding is not None:
        keymap, item = _exit_binding
        keymap.keymap_items.remove(item)
        _exit_binding = None
