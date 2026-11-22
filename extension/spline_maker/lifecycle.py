"""Keep modal previews tied to their originating Blender viewport and data."""

import bpy
from bpy.app.handlers import persistent


def tool_id(context):
    workspace = context.workspace
    tool = workspace.tools.from_space_view3d_mode(context.mode, create=False) if workspace else None
    return tool.idname if tool else None


class GestureViewport:
    def __init__(self, context):
        self.window = context.window
        self.area = context.area
        self.region = context.region
        self.workspace = context.workspace
        self.scene = getattr(context, "scene", None)
        self.mode = context.mode
        self.object = getattr(context, "edit_object", None)
        self.data = self.object.data if self.object else None
        self.tool = tool_id(context)

    def matches(self, context):
        return (
            context.window == self.window and context.area == self.area
            and context.region == self.region and context.workspace == self.workspace
            and getattr(context, "scene", None) == self.scene
            and context.area.type == "VIEW_3D" and context.region_data is not None
            and context.mode == self.mode and getattr(context, "edit_object", None) == self.object
            and (self.object is None or (len(context.objects_in_mode) == 1 and self.object.data == self.data))
            and tool_id(context) == self.tool
        )

    def available(self):
        context = bpy.context
        try:
            if (context.window_manager is None
                    or not any(window == self.window for window in context.window_manager.windows)
                    or not any(area == self.area for area in self.window.screen.areas)
                    or not any(region == self.region for region in self.area.regions)):
                return False
            with context.temp_override(window=self.window, area=self.area, region=self.region):
                return self.matches(context)
        except ReferenceError:
            return False

    def redraw(self, *, clear_header=False):
        try:
            if clear_header:
                self.area.header_text_set(None)
            self.area.tag_redraw()
        except ReferenceError:
            pass


def active_gestures():
    from . import drawing_probe, edit_drag, insert_vertex, tangent_drag, vertex_selection

    return (drawing_probe._active, edit_drag._active, insert_vertex._active,
            tangent_drag._active, vertex_selection._gesture)


def check_gestures():
    for gesture in active_gestures():
        if gesture is not None and not gesture.viewport.available():
            gesture.cancel(bpy.context)
    return 0.1 if any(active_gestures()) else None


def watch():
    # Blender can remove a window's modal handlers or change tools without
    # delivering another event to the gesture.
    if not bpy.app.background and not bpy.app.timers.is_registered(check_gestures):
        bpy.app.timers.register(check_gestures, first_interval=0.1)


@persistent
def before_data_change(_):
    from . import display, region_selection, transform_gizmos

    for gesture in active_gestures():
        if gesture is not None:
            gesture.cancel(bpy.context)
    if bpy.app.timers.is_registered(check_gestures):
        bpy.app.timers.unregister(check_gestures)
    display.reset_native_handles()
    region_selection.clear_cache()
    transform_gizmos.clear_cache()


@persistent
def after_load(_):
    from .ui import reset_sidebar_following

    reset_sidebar_following()
    for manager in bpy.data.window_managers:
        manager.property_unset("spline_maker_selection_level")
        manager.property_unset("spline_maker_vertex_rotation")
        manager.property_unset("spline_maker_bright_curves")
        manager.property_unset("spline_maker_curve_color")
    if not bpy.app.background:
        # Workspace tool setup publishes UI messages. Wait until Blender has
        # initialized the loaded window manager and its message bus.
        bpy.app.timers.register(reset_tools)


def reset_tools():
    # Activate the native tool through the same viewport operator as Blender's toolbar.
    if bpy.app.background:
        return
    context = bpy.context
    for manager in bpy.data.window_managers:
        for window in manager.windows:
            area = next((item for item in window.screen.areas if item.type == "VIEW_3D"), None)
            if area is None:
                continue
            region = next((item for item in area.regions if item.type == "WINDOW"), None)
            if region is None:
                continue
            with context.temp_override(window=window, area=area, region=region):
                if (tool_id(context) or "").startswith("spline_maker.") and bpy.ops.wm.tool_set_by_id.poll():
                    bpy.ops.wm.tool_set_by_id(name="builtin.select_box", space_type="VIEW_3D")


_HANDLERS = (
    (bpy.app.handlers.save_pre, before_data_change),
    (bpy.app.handlers.load_pre, before_data_change),
    (bpy.app.handlers.undo_pre, before_data_change),
    (bpy.app.handlers.redo_pre, before_data_change),
    (bpy.app.handlers.load_post, after_load),
)


def register():
    for handlers, callback in _HANDLERS:
        handlers.append(callback)


def unregister():
    from .ui import reset_sidebar_following

    before_data_change(None)
    reset_sidebar_following()
    if bpy.app.timers.is_registered(reset_tools):
        bpy.app.timers.unregister(reset_tools)
    reset_tools()
    for handlers, callback in _HANDLERS:
        handlers.remove(callback)
