"""Modal straight-point drawing probe for SM-003."""

import blf
import bpy
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader

from .drawing_plane import DrawingPlane, DrawingSession, project_view_point


_active = None
_exit_binding = None
_BUTTONS = (("Finish", 84, 160), ("Cancel", 168, 244))


def is_finish_press(event):
    return event.type in {"RET", "NUMPAD_ENTER", "RIGHTMOUSE"} and not (
        event.alt or event.ctrl or event.shift or event.oskey
    )


def commit_curve(context, session):
    curve = bpy.data.curves.new("Spline Maker Plane Test", "CURVE")
    curve.dimensions = "3D"
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(session.points) - 1)
    for point, coordinate in zip(spline.bezier_points, session.points):
        point.co = coordinate
        point.handle_left_type = point.handle_right_type = "VECTOR"

    obj = bpy.data.objects.new(curve.name, curve)
    context.collection.objects.link(obj)
    obj.location = session.plane.origin
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
    bl_description = "Test straight-point drawing on the starting view plane"
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
        if self.place_on_invoke:
            pixel = (event.mouse_x - context.region.x, event.mouse_y - context.region.y)
            point = self.project(context, pixel)
            if point is not None:
                self.session.place(point)
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

    def finish(self, context):
        if len(self.session.points) < 2:
            self.report({"INFO"}, "Place at least two points to finish")
            return {"RUNNING_MODAL"}
        try:
            commit_curve(context, self.session)
        finally:
            self.cleanup()
        return {"FINISHED"}

    def project(self, context, pixel):
        return project_view_point(
            self.session.plane, context.region, context.region_data, pixel
        )

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
        context.area.tag_redraw()

        if event.value == "PRESS":
            if event.type == "ESC":
                self.cleanup()
                return {"CANCELLED"}
            # Keep the scene undo stack untouched while preview points exist.
            if event.type == "Z" and event.ctrl and not (event.alt or event.oskey):
                if not event.shift:
                    self.session.undo_point()
                return {"RUNNING_MODAL"}
            if not inside:
                return {"PASS_THROUGH"}
            # Modified right-clicks must reach Blender, including Industry
            # Compatible's Alt+RMB viewport zoom.
            if is_finish_press(event):
                return self.finish(context)
            if event.type == "BACK_SPACE":
                self.session.undo_point()
                return {"RUNNING_MODAL"}
            if event.type == "LEFTMOUSE" and not (event.alt or event.ctrl or event.oskey):
                for label, left, right in _BUTTONS:
                    if left <= pixel[0] < right and 45 <= pixel[1] < 71:
                        if label == "Finish":
                            return self.finish(context)
                        self.cleanup()
                        return {"CANCELLED"}
                point = self.project(context, pixel)
                if point is not None:
                    self.session.place(point)
                return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

    def draw_overlay(self):
        context = bpy.context
        if (
            _active is not self or self.context_key(context) != self.target
            or context.region_data is None
        ):
            return
        plane = self.session.plane
        points = list(self.session.points)
        preview = self.project(context, self.pointer) if self.pointer is not None else None
        if preview is not None:
            points.append(preview)
        screen = [
            view3d_utils.location_3d_to_region_2d(context.region, context.region_data, plane.to_world(p))
            for p in points
        ]
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        segments = [p for a, b in zip(screen, screen[1:]) if a is not None and b is not None for p in (a, b)]
        draw_batch(shader, "LINES", segments, (0.25, 0.8, 1.0, 1.0))
        markers = [
            xy for p in screen[:len(self.session.points)] if p is not None
            for xy in ((p.x - 4, p.y), (p.x + 4, p.y), (p.x, p.y - 4), (p.x, p.y + 4))
        ]
        draw_batch(shader, "LINES", markers, (0.25, 0.8, 1.0, 1.0))

        for label, left, right in _BUTTONS:
            draw_batch(shader, "TRI_FAN", [(left, 45), (right, 45), (right, 71), (left, 71)],
                       (0.1, 0.15, 0.22, 1.0))
            draw_text(left + 11, 53, label)
        status = f"{len(self.session.points)} points   |   Click to place   |   Ctrl+Z or Backspace to remove"
        if self.pointer is not None and preview is None:
            status = "Placement unavailable. Orbit to face the drawing plane."
        draw_text(84, 81, status)


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
