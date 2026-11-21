"""Readable source-curve overlay and viewport display controls."""

import blf
import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d

from .drawing_probe import draw_batch
from . import segment_selection, region_selection

_handler = None


def redraw(self, context):
    for manager in bpy.data.window_managers:
        for window in manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()


def active(context):
    from .vertex_selection import supported_curve
    return (context.area is not None and context.area.type == "VIEW_3D"
            and context.region is not None and context.region.type == "WINDOW"
            and context.region_data is not None
            and (context.mode == "OBJECT" or supported_curve(context))
            and context.space_data.overlay.show_overlays
            and context.window_manager.spline_maker_bright_curves)


def draw():
    context = bpy.context
    if active(context):
        draw_curves(context)
    draw_transform_readout(context)


def draw_curves(context):
    if context.mode == "OBJECT":
        lines = []
        for obj in object_curves(context):
            projected = segment_selection.projected_segments(obj.data, obj.matrix_world,
                lambda p: location_3d_to_region_2d(context.region, context.region_data, p), include_hidden=True)
            lines.extend(p for _, edges in projected for edge in edges for p in edge)
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        draw_batch(shader, "LINES", lines, (*context.window_manager.spline_maker_curve_color, 1.0))
        return
    projected = segment_selection.viewport_segments(context)
    from .feasibility import active_mode
    if active_mode(context) is not None and segment_selection.composite(context):
        selected = region_selection.outline_keys(context)
    else:
        selected = {key for key, a, b in segment_selection.segments(context.edit_object.data)
                    if a.select_control_point and b.select_control_point}
    plain = [p for key, edges in projected if key not in selected for edge in edges for p in edge]
    chosen = [p for key, edges in projected if key in selected for edge in edges for p in edge]
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    draw_batch(shader, "LINES", plain, (*context.window_manager.spline_maker_curve_color, 1.0))
    draw_batch(shader, "LINES", chosen, (0.35, 0.72, 1.0, 1.0))


def draw_transform_readout(context):
    from .tangent_drag import _active
    if (_active is None or context.window is None or context.area is None or context.region is None
            or tuple(item.as_pointer() for item in (context.window, context.area, context.region)) != _active.key
            or not _active.viewport.matches(context)):
        return
    center = location_3d_to_region_2d(context.region, context.region_data, _active.center_world)
    if center is None:
        return
    font = 0
    blf.size(font, 14)
    width, height = blf.dimensions(font, _active.readout)
    offset = 95 * context.preferences.system.ui_scale
    x = center.x + offset
    if x + width + 12 > context.region.width:
        x = center.x - offset - width
    x = max(8, min(x, context.region.width - width - 12))
    y = max(8, min(center.y + 12, context.region.height - height - 18))
    background = ((x - 6, y - 5), (x + width + 6, y - 5),
                  (x + width + 6, y + height + 5), (x - 6, y + height + 5))
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    draw_batch(shader, "TRI_FAN", background, (0.08, 0.1, 0.13, 1.0))
    blf.position(font, x, y, 0)
    blf.color(font, 1.0, 1.0, 1.0, 1.0)
    blf.draw(font, _active.readout)


def object_curves(context):
    # Keep Blender's native selection outline on selected objects. Point.hide
    # only affects Edit Mode; it must not erase visible Object Mode geometry.
    return [obj for obj in context.visible_objects if obj.type == "CURVE" and not obj.select_get()
            and obj.data.splines and all(s.type == "BEZIER" for s in obj.data.splines)]


def draw_settings(layout, context):
    layout.separator()
    layout.label(text="Curve display")
    if context.mode == "EDIT_CURVE":
        layout.prop(context.space_data.overlay, "show_curve_normals", text="Direction wings (normals)")
    layout.prop(context.window_manager, "spline_maker_bright_curves", text="Bright spline overlay")
    row = layout.row()
    row.enabled = context.window_manager.spline_maker_bright_curves
    row.prop(context.window_manager, "spline_maker_curve_color", text="Spline color")


def register():
    global _handler
    bpy.types.WindowManager.spline_maker_bright_curves = bpy.props.BoolProperty(
        name="Bright spline overlay", default=True, options={"SKIP_SAVE"}, update=redraw,
    )
    bpy.types.WindowManager.spline_maker_curve_color = bpy.props.FloatVectorProperty(
        name="Spline color", subtype="COLOR", size=3, min=0, max=1,
        default=(0.65, 0.8, 0.95), options={"SKIP_SAVE"}, update=redraw,
    )
    if not bpy.app.background:
        _handler = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")


def unregister():
    global _handler
    if _handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handler, "WINDOW")
        _handler = None
    for manager in bpy.data.window_managers:
        manager.property_unset("spline_maker_bright_curves")
        manager.property_unset("spline_maker_curve_color")
    del bpy.types.WindowManager.spline_maker_bright_curves
    del bpy.types.WindowManager.spline_maker_curve_color
    redraw(None, bpy.context)
