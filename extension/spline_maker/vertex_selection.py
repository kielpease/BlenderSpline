"""Screen-space Bézier picking backed by Blender's edit selection flags."""

from dataclasses import dataclass

import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Vector

from .drawing_probe import draw_batch
from .feasibility import active_mode, editable_bezier_points
from . import edit_drag, lifecycle, segment_selection
from .edit_snapping import SHIFT_KEYS
from .drag_navigation import DragNavigation


_COMPONENTS = (
    ("co", "select_control_point"),
    ("handle_left", "select_left_handle"),
    ("handle_right", "select_right_handle"),
)
_PICK_RADIUS = 9
_DRAG_THRESHOLD = 5
_gesture = None
_handler = None
_cursor_handler = None
_bindings = []


@dataclass
class Component:
    point: bpy.types.BezierSplinePoint
    coordinate: str
    selection: str
    pixel: tuple

    @property
    def selected(self):
        return getattr(self.point, self.selection)

    def select(self, value):
        setattr(self.point, self.selection, value)


def supported_curve(context):
    obj = context.edit_object
    return (
        context.mode == "EDIT_CURVE" and obj is not None
        and len(context.objects_in_mode) == 1
        and all(spline.type == "BEZIER" for spline in obj.data.splines)
    )


def selection_active(context):
    return (
        context.area is not None and context.area.type == "VIEW_3D"
        and context.region is not None and context.region.type == "WINDOW"
        and context.region_data is not None
        and context.space_data.overlay.show_overlays
        and active_mode(context) is not None and supported_curve(context)
    )


def project_components(points, matrix_world, project, handle_display):
    for point in points:
        handles_visible = handle_display == "ALL" or (
            handle_display == "SELECTED" and any(getattr(point, attr) for _, attr in _COMPONENTS)
        )
        for coord, attr in _COMPONENTS:
            if coord != "co" and not handles_visible:
                continue
            pixel = project(matrix_world @ getattr(point, coord))
            if pixel is not None:
                yield Component(point, coord, attr, tuple(pixel))


def viewport_components(context):
    return project_components(
        editable_bezier_points(context), context.edit_object.matrix_world,
        lambda world: location_3d_to_region_2d(context.region, context.region_data, world),
        "ALL",  # Direct manipulation diamonds remain available in every tool.
    )


def pick_component(components, pixel):
    closest = None
    best = (_PICK_RADIUS ** 2, 1)
    for component in components:
        x, y = component.pixel
        score = ((x - pixel[0]) ** 2 + (y - pixel[1]) ** 2, component.coordinate != "co")
        if score[0] <= _PICK_RADIUS ** 2 and (closest is None or score < best):
            closest, best = component, score
    return closest


def click_select(points, component, *, extend):
    if not extend:
        clear_selection(points)
    if component is not None:
        component.select(not component.selected if extend else True)


def clear_selection(points):
    for point in points:
        for _, attr in _COMPONENTS:
            setattr(point, attr, False)


def box_select(points, components, start, end, *, extend):
    xmin, xmax = sorted((start[0], end[0]))
    ymin, ymax = sorted((start[1], end[1]))
    if not extend:
        clear_selection(points)
    for component in components:
        x, y = component.pixel
        if component.coordinate == "co" and xmin <= x <= xmax and ymin <= y <= ymax:
            component.select(True)


def viewport_key(context):
    return tuple(item.as_pointer() for item in (context.window, context.area, context.region))


def pointer_in_viewport(context, window_pixel):
    region = context.region
    mouse_x, mouse_y = window_pixel
    x, y = mouse_x - region.x, mouse_y - region.y
    if not (0 <= x < region.width and 0 <= y < region.height):
        return None
    for other in context.area.regions:
        if other.type in {"UI", "TOOLS"} and (
            other.x <= mouse_x < other.x + other.width
            and other.y <= mouse_y < other.y + other.height
        ):
            return None
    return x, y


class SPLINE_MAKER_OT_vertex_select(bpy.types.Operator):
    bl_idname = "spline_maker.vertex_select"
    bl_label = "Select Spline Vertices"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context):
        return selection_active(context) and _gesture is None and edit_drag._active is None

    def invoke(self, context, event):
        global _gesture
        pixel = pointer_in_viewport(context, (event.mouse_x, event.mouse_y))
        if pixel is None:
            return {"PASS_THROUGH"}
        hit = pick_component(viewport_components(context), pixel)
        self.handle_key = None
        if hit is not None and hit.coordinate != "co":
            self.data = context.edit_object.data
            self.obj = context.edit_object
            if abs(self.obj.matrix_world.determinant()) < 1e-12:
                return {"CANCELLED"}
            self.handle_key = next(
                (si, pi, hit.coordinate, hit.selection)
                for si, spline in enumerate(self.data.splines)
                for pi, point in enumerate(spline.bezier_points) if point == hit.point
            )
            self.handle_state = edit_drag.snapshot(hit.point)
            si, pi, coordinate, _ = self.handle_key
            neighbor = edit_drag.handle_neighbor(self.data.splines[si], pi, coordinate)
            self.handle_anchor = self.obj.matrix_world @ hit.point.co
            basis = self.obj.matrix_world.to_3x3()
            self.handle_directions = [basis @ Vector((1, 0, 0)), basis @ Vector((0, 1, 0))]
            if neighbor is not None:
                self.handle_directions.insert(0, basis @ (neighbor - hit.point.co))
            self.selection_state = [
                (si, pi, tuple(getattr(point, flag) for _, flag in _COMPONENTS))
                for si, spline in enumerate(self.data.splines)
                for pi, point in enumerate(spline.bezier_points)
            ]
            self.plane_origin = self.obj.matrix_world @ getattr(hit.point, hit.coordinate)
            self.plane_normal = context.region_data.view_rotation @ Vector((0, 0, 1))
            self.world_start = edit_drag.project(context, pixel, self.plane_origin, self.plane_normal)
            self.world_delta = self.base_delta = Vector((0, 0, 0))
            self.inverse = self.obj.matrix_world.inverted().to_3x3()
            if self.world_start is None:
                return {"CANCELLED"}
        else:
            # Gizmos own their actual hit area. Let Blender dispatch the gizmo
            # event instead of starting a marquee over its arrows/rings/pads.
            from .transform_gizmos import gizmo_highlighted
            if gizmo_highlighted(context):
                return {"PASS_THROUGH"}
        self.key = viewport_key(context)
        self.viewport = lifecycle.GestureViewport(context)
        self.navigation = DragNavigation(context)
        self.start = self.end = pixel
        self.extend = event.shift
        self.dragging = False
        self.handle_moved = False
        _gesture = self
        context.window_manager.modal_handler_add(self)
        lifecycle.watch()
        return {"RUNNING_MODAL"}

    def cleanup(self, context):
        global _gesture
        if _gesture is self:
            _gesture = None
            self.viewport.redraw()

    def cancel(self, context):
        if _gesture is not self:
            return
        if self.handle_moved:
            try:
                si, pi, _, _ = self.handle_key
                edit_drag.restore(self.data.splines[si].bezier_points[pi], self.handle_state)
                for si, pi, flags in self.selection_state:
                    point = self.data.splines[si].bezier_points[pi]
                    for (_, flag), value in zip(_COMPONENTS, flags):
                        setattr(point, flag, value)
                self.data.update_tag()
            except (ReferenceError, IndexError):
                pass
        self.cleanup(context)

    def modal(self, context, event):
        if _gesture is not self or not self.viewport.matches(context) or not selection_active(context):
            self.cancel(context)
            return {"CANCELLED", "PASS_THROUGH"}
        if self.navigation.forward(event):
            return {"PASS_THROUGH"}
        if (event.type in {"ESC", "WINDOW_DEACTIVATE"} or (event.ctrl and event.type == "Z")
                or (event.type == "RIGHTMOUSE" and event.value == "PRESS")):
            self.cancel(context)
            return {"CANCELLED"}
        releasing = event.type == "LEFTMOUSE" and event.value == "RELEASE"
        shift_changed = self.dragging and self.handle_key is not None and event.type in SHIFT_KEYS
        if not releasing and not shift_changed and event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"PASS_THROUGH"}
        region = context.region
        pixel = (
            min(max(event.mouse_x - region.x, 0), region.width - 1),
            min(max(event.mouse_y - region.y, 0), region.height - 1),
        )
        if self.navigation.rebase(context):
            if self.handle_key is not None:
                self.base_delta = self.world_delta
                self.plane_normal = context.region_data.view_rotation @ Vector((0, 0, 1))
                self.world_start = edit_drag.project(
                    context, pixel, self.plane_origin + self.base_delta, self.plane_normal
                )
            if not self.dragging:
                self.start = self.end = pixel
            if self.handle_key is not None or not self.dragging or not releasing:
                if releasing:
                    self.cleanup(context)
                    return {"FINISHED"} if self.handle_moved else {"CANCELLED"}
                return {"RUNNING_MODAL"}
        else:
            self.end = pixel
        dx, dy = self.end[0] - self.start[0], self.end[1] - self.start[1]
        self.dragging = self.dragging or dx * dx + dy * dy >= _DRAG_THRESHOLD ** 2
        context.area.tag_redraw()
        if self.dragging and self.handle_key is not None:
            hit = edit_drag.project(
                context, self.end, self.plane_origin + self.base_delta, self.plane_normal
            )
            if self.world_start is None:
                self.world_start = hit
            elif hit is not None:
                si, pi, coordinate, flag = self.handle_key
                point = self.data.splines[si].bezier_points[pi]
                if not self.handle_moved:
                    if not segment_selection.composite(context):
                        if not self.extend:
                            clear_selection(editable_bezier_points(context))
                        setattr(point, flag, True)
                self.handle_moved = True
                delta = self.base_delta + hit - self.world_start
                if event.shift:
                    position = self.plane_origin + delta
                    snapped = edit_drag.snap_handle(
                        context, position, self.handle_anchor, self.handle_directions, self.plane_normal
                    )
                    delta = snapped - self.plane_origin
                self.world_delta = delta
                edit_drag.translate_handle(point, self.handle_state, coordinate,
                                           self.inverse @ delta)
                self.data.update_tag()
            if releasing:
                self.cleanup(context)
                return {"FINISHED"}
            return {"RUNNING_MODAL"}
        if not releasing:
            return {"RUNNING_MODAL"}

        points = tuple(editable_bezier_points(context))
        components = list(viewport_components(context))
        if segment_selection.level(context) in {"REGION", "WHOLE"}:
            from . import region_selection
            reason = (region_selection.box(context, self.start, self.end, extend=self.extend) if self.dragging
                      else region_selection.click(context, self.end, extend=self.extend))
            if reason:
                self.report({"WARNING"}, reason)
        elif segment_selection.is_active(context):
            projected = segment_selection.viewport_segments(context)
            if self.dragging:
                segment_selection.box(context.edit_object.data, projected, self.start, self.end, extend=self.extend)
            else:
                segment_selection.click(context.edit_object.data, projected, self.end, extend=self.extend)
        elif self.dragging:
            box_select(points, components, self.start, self.end, extend=self.extend)
        else:
            click_select(points, pick_component(components, self.end), extend=self.extend)
        context.edit_object.data.update_tag()
        self.cleanup(context)
        return {"FINISHED"}


def marker_lines(component, size):
    x, y = component.pixel
    vertices = (
        ((x - size, y - size), (x + size, y - size), (x + size, y + size), (x - size, y + size))
        if component.coordinate == "co"
        else ((x, y - size), (x + size, y), (x, y + size), (x - size, y))
    )
    return [point for edge in zip(vertices, vertices[1:] + vertices[:1]) for point in edge]


def draw_selection():
    context = bpy.context
    if not selection_active(context):
        return
    key = viewport_key(context)
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    components = list(viewport_components(context))
    if segment_selection.composite(context):
        from .region_selection import outline_keys
        keys = outline_keys(context)
        edges = [pixel for key, edges in segment_selection.viewport_segments(context) if key in keys
                 for edge in edges for pixel in edge]
        draw_batch(shader, "LINES", edges, (0.35, 0.72, 1.0, 1.0))
    selected = [pixel for component in components if component.selected
                for pixel in marker_lines(component, 7)]
    handles = [pixel for component in components if component.coordinate != "co"
               for pixel in marker_lines(component, 4)]
    draw_batch(shader, "LINES", handles, (0.65, 0.75, 0.8, 1.0))
    guides = [pixel for component in components if component.coordinate != "co"
              for pixel in (location_3d_to_region_2d(context.region, context.region_data,
                            context.edit_object.matrix_world @ component.point.co), component.pixel)]
    if all(pixel is not None for pixel in guides):
        draw_batch(shader, "LINES", guides, (0.4, 0.5, 0.55, 0.65))
    draw_batch(shader, "LINES", selected, (0.35, 0.72, 1.0, 1.0))
    if (_gesture is not None and _gesture.key == key and _gesture.viewport.matches(context) and _gesture.dragging
            and _gesture.handle_key is None):
        x1, y1 = _gesture.start
        x2, y2 = _gesture.end
        corners = ((x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1))
        draw_batch(shader, "LINES", [p for edge in zip(corners, corners[1:]) for p in edge],
                   (0.45, 1.0, 0.78, 1.0))


def draw_hover(window_pixel):
    context = bpy.context
    if not selection_active(context) or _gesture is not None:
        return
    pointer = pointer_in_viewport(context, window_pixel)
    if pointer is None:
        return
    hit = pick_component(viewport_components(context), pointer)
    if segment_selection.composite(context) and (hit is None or hit.coordinate == "co"):
        projected = segment_selection.viewport_segments(context)
        if segment_selection.is_active(context):
            key = segment_selection.pick(projected, pointer)
            keys = {key} if key is not None else set()
        else:
            from .region_selection import hover_keys
            keys = hover_keys(context, pointer, projected)
        if keys:
            region = context.region
            lines = [(p[0] + region.x, p[1] + region.y)
                     for candidate, edges in projected if candidate in keys for edge in edges for p in edge]
            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            draw_batch(shader, "LINES", lines, (0.45, 1.0, 0.78, 1.0))
        return
    if hit is not None:
        # Cursor overlays draw in window pixels; mesh projection is region-local.
        region = context.region
        outline = [(x + region.x, y + region.y) for x, y in marker_lines(hit, 10)]
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        draw_batch(shader, "LINES", outline, (0.45, 1.0, 0.78, 1.0))


def register():
    global _handler, _cursor_handler
    if not bpy.app.background:
        _handler = bpy.types.SpaceView3D.draw_handler_add(draw_selection, (), "WINDOW", "POST_PIXEL")
        _cursor_handler = bpy.types.WindowManager.draw_cursor_add(draw_hover, (), "VIEW_3D", "WINDOW")
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is not None:
        keymap = keyconfig.keymaps.new(name="Curve", space_type="EMPTY", region_type="WINDOW")
        for shift in (False, True):
            item = keymap.keymap_items.new(
                SPLINE_MAKER_OT_vertex_select.bl_idname, "LEFTMOUSE", "PRESS",
                head=True, shift=shift,
            )
            _bindings.append((keymap, item))


def unregister():
    global _handler, _cursor_handler, _gesture
    if _cursor_handler is not None:
        bpy.types.WindowManager.draw_cursor_remove(_cursor_handler)
        _cursor_handler = None
    if _handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handler, "WINDOW")
        _handler = None
    stop_active(bpy.context)
    for keymap, item in _bindings:
        keymap.keymap_items.remove(item)
    _bindings.clear()


CLASSES = (SPLINE_MAKER_OT_vertex_select,)


def stop_active(context):
    if _gesture is not None:
        _gesture.cancel(context)
