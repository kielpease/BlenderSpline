"""Logical Bézier segments, adaptive screen-space picking, native selection storage."""

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d

from .feasibility import active_mode

_bindings = []
LEVELS = (("VERTEX", "Vertex", ""), ("SEGMENT", "Segment", ""),
          ("REGION", "Spline", ""), ("WHOLE", "Whole curve", ""))


def level(context):
    return getattr(context.window_manager, "spline_maker_selection_level", "VERTEX")


def composite(context):
    return level(context) != "VERTEX"


def is_active(context):
    return level(context) == "SEGMENT"


def segments(data, *, include_hidden=False):
    for si, spline in enumerate(data.splines):
        if spline.type != "BEZIER":
            continue
        points = spline.bezier_points
        count = len(points)
        for start in range(count if spline.use_cyclic_u and count > 1 else max(count - 1, 0)):
            end = (start + 1) % count
            a, b = points[start], points[end]
            if include_hidden or (not a.hide and not b.hide):
                yield (si, start), a, b


def selected(data):
    # Outgoing/incoming handle flags encode each edge independently. Anchor
    # flags contain the endpoint union. All are part of native Curve Edit undo.
    return {key for key, a, b in segments(data)
            if a.select_control_point and b.select_control_point
            and a.select_right_handle and b.select_left_handle}


def endpoints(data, keys):
    result = set()
    for (si, start), _, _ in segments(data):
        if (si, start) in keys:
            result.update(((si, start), (si, (start + 1) % len(data.splines[si].bezier_points))))
    return result


def select(data, keys):
    valid = {key for key, _, _ in segments(data)} & set(keys)
    for spline in data.splines:
        if spline.type == "BEZIER":
            for point in spline.bezier_points:
                if not point.hide:
                    point.select_control_point = point.select_left_handle = point.select_right_handle = False
    for key, a, b in segments(data):
        if key in valid:
            a.select_control_point = b.select_control_point = True
            a.select_right_handle = b.select_left_handle = True
    data.update_tag()


def distance_squared(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length)) if length else 0
    return (point[0] - a[0] - t * dx) ** 2 + (point[1] - a[1] - t * dy) ** 2


def curve_edges(controls, project, depth=0):
    """de Casteljau subdivision with 0.75-pixel flatness and near-plane breaks."""
    pixels = [project(point) for point in controls]
    visible = all(point is not None for point in pixels)
    if visible and (depth >= 10 or max(distance_squared(p, pixels[0], pixels[3])
                                      for p in pixels[1:3]) <= 0.75 ** 2):
        return [(tuple(pixels[0]), tuple(pixels[3]))]
    if depth >= 10 or all(point is None for point in pixels):
        return []
    a, b, c, d = controls
    ab, bc, cd = (a + b) / 2, (b + c) / 2, (c + d) / 2
    abc, bcd = (ab + bc) / 2, (bc + cd) / 2
    middle = (abc + bcd) / 2
    return (curve_edges((a, ab, abc, middle), project, depth + 1)
            + curve_edges((middle, bcd, cd, d), project, depth + 1))


def projected_segments(data, matrix, project, *, include_hidden=False):
    return [(key, curve_edges(tuple(matrix @ p for p in (a.co, a.handle_right, b.handle_left, b.co)), project))
            for key, a, b in segments(data, include_hidden=include_hidden)]


def viewport_segments(context):
    return projected_segments(context.edit_object.data, context.edit_object.matrix_world,
        lambda p: location_3d_to_region_2d(context.region, context.region_data, p))


def pick(projected, pixel):
    best, hit = 9 ** 2, None
    for key, edges in projected:
        distance = min((distance_squared(pixel, a, b) for a, b in edges), default=float("inf"))
        if distance <= best and (hit is None or distance < best):
            best, hit = distance, key
    return hit


def click(data, projected, pixel, *, extend):
    keys = selected(data) if extend else set()
    hit = pick(projected, pixel)
    if hit is not None:
        keys.symmetric_difference_update({hit}) if extend else keys.add(hit)
    select(data, keys)


def edge_intersects_box(a, b, bounds):
    """Inclusive line/rectangle clipping, including crossings with both ends outside."""
    xmin, xmax, ymin, ymax = bounds
    first, last = 0.0, 1.0
    for origin, delta, minimum, maximum in (
        (a[0], b[0] - a[0], xmin, xmax),
        (a[1], b[1] - a[1], ymin, ymax),
    ):
        if delta == 0:
            if origin < minimum or origin > maximum:
                return False
            continue
        entry, exit = sorted(((minimum - origin) / delta, (maximum - origin) / delta))
        first, last = max(first, entry), min(last, exit)
        if first > last:
            return False
    return True


def box(data, projected, start, end, *, extend):
    xmin, xmax = sorted((start[0], end[0]))
    ymin, ymax = sorted((start[1], end[1]))
    keys = selected(data) if extend else set()
    for key, edges in projected:
        if any(edge_intersects_box(a, b, (xmin, xmax, ymin, ymax)) for a, b in edges):
            keys.add(key)
    select(data, keys)


class SPLINE_MAKER_OT_selection_level(bpy.types.Operator):
    bl_idname = "spline_maker.selection_level"
    bl_label = "Set Splines Selection Level"
    bl_description = "Choose vertices, segments, individual splines, or all source curve geometry"
    bl_options = {"INTERNAL"}

    target: bpy.props.EnumProperty(items=LEVELS)

    @classmethod
    def poll(cls, context):
        from .vertex_selection import supported_curve
        return (context.area is not None and context.area.type == "VIEW_3D"
                and active_mode(context) is not None and supported_curve(context))

    def execute(self, context):
        from . import vertex_selection, edit_drag, tangent_drag, region_selection
        vertex_selection.stop_active(context)
        edit_drag.unregister()
        tangent_drag.unregister()
        old = context.window_manager.spline_maker_selection_level
        if self.target == "REGION":
            reason = region_selection.unavailable_reason(context.edit_object.data)
            if reason:
                self.report({"WARNING"}, reason)
                return {"CANCELLED"}
        if old != self.target:
            if self.target == "REGION":
                region_selection.select_regions(context.edit_object.data, set())
            elif self.target == "SEGMENT":
                select(context.edit_object.data, set())
            elif self.target == "VERTEX":
                # Retain endpoints, discard the edge-code handle selections.
                for spline in context.edit_object.data.splines:
                    for point in spline.bezier_points:
                        point.select_left_handle = point.select_right_handle = False
            context.window_manager.spline_maker_selection_level = self.target
            context.edit_object.data.update_tag()
        if self.target == "REGION" and len(context.edit_object.data.splines) == 1:
            # Repeating 3 reselects the single spline after empty-space deselect.
            region_selection.select_regions(context.edit_object.data, {0})
        elif self.target == "WHOLE":
            region_selection.select_whole(context.edit_object.data, True)
        context.area.tag_redraw()
        return {"FINISHED"}


class SPLINE_MAKER_OT_enter_selection_level(bpy.types.Operator):
    bl_idname = "spline_maker.enter_selection_level"
    bl_label = "Enter Splines Selection"
    bl_description = "Choose a Splines selection level directly from Bézier Curve Edit Mode"
    bl_options = {"INTERNAL"}

    target: bpy.props.EnumProperty(items=LEVELS)

    @classmethod
    def poll(cls, context):
        from .feasibility import SPLINE_MAKER_OT_switch_tangent_tool
        return SPLINE_MAKER_OT_switch_tangent_tool.poll(context)

    def execute(self, context):
        if active_mode(context) is None:
            result = bpy.ops.spline_maker.switch_tangent_tool(target="SELECT")
            if result != {"FINISHED"}:
                return result
        return bpy.ops.spline_maker.selection_level(target=self.target)


def register():
    bpy.types.WindowManager.spline_maker_selection_level = bpy.props.EnumProperty(
        items=LEVELS,
        default="VERTEX", options={"SKIP_SAVE"},
    )
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is not None:
        for name, space in (("Curve", "EMPTY"), ("3D View", "VIEW_3D")):
            keymap = keyconfig.keymaps.new(name=name, space_type=space, region_type="WINDOW")
            for key, target in (("ONE", "VERTEX"), ("TWO", "SEGMENT"), ("THREE", "REGION"), ("FOUR", "WHOLE")):
                item = keymap.keymap_items.new("spline_maker.enter_selection_level", key, "PRESS", head=True)
                item.properties.target = target
                _bindings.append((keymap, item))


def unregister():
    for keymap, item in _bindings:
        keymap.keymap_items.remove(item)
    _bindings.clear()
    for manager in bpy.data.window_managers:
        manager.property_unset("spline_maker_selection_level")
    del bpy.types.WindowManager.spline_maker_selection_level


CLASSES = (SPLINE_MAKER_OT_selection_level, SPLINE_MAKER_OT_enter_selection_level)
