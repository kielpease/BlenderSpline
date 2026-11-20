"""Screen-space Bézier picking backed by Blender's edit selection flags."""

from dataclasses import dataclass

import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d

from .drawing_probe import draw_batch
from .feasibility import active_mode, editable_bezier_points


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
        and active_mode(context) == "SELECT" and supported_curve(context)
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
        context.space_data.overlay.display_handle,
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
    bl_label = "Select Spline Maker Vertices"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context):
        return selection_active(context) and _gesture is None

    def invoke(self, context, event):
        global _gesture
        pixel = pointer_in_viewport(context, (event.mouse_x, event.mouse_y))
        if pixel is None:
            return {"PASS_THROUGH"}
        self.key = viewport_key(context)
        self.start = self.end = pixel
        self.extend = event.shift
        self.dragging = False
        _gesture = self
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        global _gesture
        if _gesture is self:
            _gesture = None
            if context.area is not None:
                context.area.tag_redraw()

    def modal(self, context, event):
        if _gesture is not self or not selection_active(context) or viewport_key(context) != self.key:
            self.cancel(context)
            return {"CANCELLED"}
        if event.type == "ESC" or event.type == "WINDOW_DEACTIVATE":
            self.cancel(context)
            return {"CANCELLED"}
        releasing = event.type == "LEFTMOUSE" and event.value == "RELEASE"
        if not releasing and event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"PASS_THROUGH"}
        region = context.region
        self.end = (
            min(max(event.mouse_x - region.x, 0), region.width - 1),
            min(max(event.mouse_y - region.y, 0), region.height - 1),
        )
        dx, dy = self.end[0] - self.start[0], self.end[1] - self.start[1]
        self.dragging = self.dragging or dx * dx + dy * dy >= _DRAG_THRESHOLD ** 2
        context.area.tag_redraw()
        if not releasing:
            return {"RUNNING_MODAL"}

        points = tuple(editable_bezier_points(context))
        components = list(viewport_components(context))
        if self.dragging:
            box_select(points, components, self.start, self.end, extend=self.extend)
        else:
            click_select(points, pick_component(components, self.end), extend=self.extend)
        context.edit_object.data.update_tag()
        self.cancel(context)
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
    selected = [pixel for component in components if component.selected
                for pixel in marker_lines(component, 7)]
    draw_batch(shader, "LINES", selected, (0.35, 0.72, 1.0, 1.0))
    if _gesture is not None and _gesture.key == key and _gesture.dragging:
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
    _gesture = None
    for keymap, item in _bindings:
        keymap.keymap_items.remove(item)
    _bindings.clear()


CLASSES = (SPLINE_MAKER_OT_vertex_select,)
