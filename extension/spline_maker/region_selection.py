"""Individual spline and whole-object geometry selection using native flags."""

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d

from . import segment_selection as segments
from .region_geometry import validate, inside

_cache_key = None
_cache_value = None


def regions(data):
    global _cache_key, _cache_value
    key = (data.as_pointer(), tuple((spline.type, spline.use_cyclic_u,
        tuple((p.hide, *p.co, *p.handle_left, *p.handle_right) for p in spline.bezier_points))
        for spline in data.splines))
    if key != _cache_key:
        _cache_key, _cache_value = key, validate(data)
    return _cache_value


def unavailable_reason(data):
    return "" if selectable_splines(data) else "No fully visible Bezier splines; unhide their vertices to select them"


def selectable_splines(data):
    # Spline selection is topological: open/nonplanar/crossed paths can still
    # be selected by their boundary. Validation only governs interior picking.
    return {index for index, spline in enumerate(data.splines)
            if spline.type == "BEZIER" and spline.bezier_points
            and not any(point.hide for point in spline.bezier_points)}


def fully_selected(spline):
    return bool(spline.bezier_points) and all(p.select_control_point and p.select_left_handle and p.select_right_handle
                                             for p in spline.bezier_points)


def selected_regions(data):
    return {index for index in selectable_splines(data) if fully_selected(data.splines[index])}


def select_regions(data, selected):
    valid = selectable_splines(data) & set(selected)
    for index, spline in enumerate(data.splines):
        for point in spline.bezier_points:
            if not point.hide:
                point.select_control_point = point.select_left_handle = point.select_right_handle = index in valid
    data.update_tag()


def whole_selected(data):
    return bool(data.splines) and all(fully_selected(spline) for spline in data.splines)


def select_whole(data, value):
    for spline in data.splines:
        for point in spline.bezier_points:
            point.select_control_point = point.select_left_handle = point.select_right_handle = value
    data.update_tag()


def region_hits(context, pixel, projected=None):
    from .edit_drag import project
    data, matrix = context.edit_object.data, context.edit_object.matrix_world
    eligible = selectable_splines(data)
    if projected is None:
        projected = segments.viewport_segments(context)
    hits = {index for (index, _), edges in projected if index in eligible
            and any(segments.distance_squared(pixel, a, b) <= 9 ** 2 for a, b in edges)}
    for index in eligible:
        for point in data.splines[index].bezier_points:
            p = location_3d_to_region_2d(context.region, context.region_data, matrix @ point.co)
            if p is not None and (p[0] - pixel[0]) ** 2 + (p[1] - pixel[1]) ** 2 <= 9 ** 2:
                hits.add(index)
    # A boundary identifies the spline even inside another closed outline.
    if hits:
        return hits, "Multiple splines under the pointer; orbit to disambiguate" if len(hits) > 1 else ""
    loops, _ = regions(data)
    if abs(matrix.determinant()) < 1e-12:
        return set(), "Object scale collapses the region"
    inverse = matrix.inverted()
    hits = set()
    for index, loop in loops.items():
        normal = (inverse.transposed().to_3x3() @ loop.normal).normalized()
        hit = project(context, pixel, matrix @ loop.origin, normal)
        if hit is not None and inside(loop.uv(inverse @ hit), loop.polygon):
            hits.add(index)
    return hits, "Multiple splines under the pointer; orbit to disambiguate" if len(hits) > 1 else ""


def outline_keys(context):
    data = context.edit_object.data
    level = segments.level(context)
    if level == "REGION":
        selected = selected_regions(data)
        return {key for key, _, _ in segments.segments(data) if key[0] in selected}
    if level == "WHOLE":
        return {key for key, _, _ in segments.segments(data)} if whole_selected(data) else set()
    return segments.selected(data)


def hover_keys(context, pixel, projected):
    level = segments.level(context)
    if level == "REGION":
        hits, reason = region_hits(context, pixel, projected)
        return {key for key, _ in projected if key[0] in hits} if not reason else set()
    if whole_hit(context, pixel, projected):
        return {key for key, _ in projected}
    return set()


def anchor_pixels(context):
    matrix = context.edit_object.matrix_world
    return [location_3d_to_region_2d(context.region, context.region_data, matrix @ p.co)
            for spline in context.edit_object.data.splines for p in spline.bezier_points if not p.hide]


def whole_hit(context, pixel, projected):
    return (segments.pick(projected, pixel) is not None
            or any(p is not None and (p[0] - pixel[0]) ** 2 + (p[1] - pixel[1]) ** 2 <= 9 ** 2
                   for p in anchor_pixels(context))
            or bool(region_hits(context, pixel, projected)[0]))


def click(context, pixel, *, extend):
    data = context.edit_object.data
    projected = segments.viewport_segments(context)
    if segments.level(context) == "WHOLE":
        hit = whole_hit(context, pixel, projected)
        if hit:
            select_whole(data, not whole_selected(data) if extend else True)
        elif not extend:
            select_whole(data, False)
        return ""
    reason = unavailable_reason(data)
    if reason:
        return reason
    hits, reason = region_hits(context, pixel, projected)
    if reason:
        return reason  # Preserve selection instead of choosing an ambiguous loop.
    selected = selected_regions(data) if extend else set()
    if hits:
        selected.symmetric_difference_update(hits) if extend else selected.update(hits)
    select_regions(data, selected)
    return ""


def box(context, start, end, *, extend):
    data = context.edit_object.data
    xmin, xmax = sorted((start[0], end[0]))
    ymin, ymax = sorted((start[1], end[1]))

    def enclosed(pixels):
        return bool(pixels) and all(p is not None and xmin <= p[0] <= xmax and ymin <= p[1] <= ymax for p in pixels)

    if segments.level(context) == "WHOLE":
        projected = segments.viewport_segments(context)
        pixels = anchor_pixels(context) + [p for _, edges in projected for edge in edges for p in edge]
        select_whole(data, enclosed(pixels) or (extend and whole_selected(data)))
        return ""
    reason = unavailable_reason(data)
    if reason:
        return reason
    selected = selected_regions(data) if extend else set()
    projected = segments.viewport_segments(context)
    for index in selectable_splines(data):
        pixels = [location_3d_to_region_2d(context.region, context.region_data,
                  context.edit_object.matrix_world @ point.co) for point in data.splines[index].bezier_points]
        pixels += [p for (si, _), edges in projected if si == index for edge in edges for p in edge]
        if enclosed(pixels):
            selected.add(index)
    select_regions(data, selected)
    return ""


class SPLINE_MAKER_OT_whole_selection(bpy.types.Operator):
    bl_idname = "spline_maker.whole_selection"
    bl_label = "Select Whole Curve Geometry"
    bl_description = "Select or deselect source geometry while keeping the active object"
    bl_options = {"UNDO", "INTERNAL"}

    action: bpy.props.EnumProperty(items=(("SELECT", "Select", ""), ("CLEAR", "Clear", "")))

    @classmethod
    def poll(cls, context):
        from .segment_selection import SPLINE_MAKER_OT_selection_level
        return SPLINE_MAKER_OT_selection_level.poll(context) and segments.level(context) == "WHOLE"

    def execute(self, context):
        select_whole(context.edit_object.data, self.action == "SELECT")
        context.area.tag_redraw()
        return {"FINISHED"}


def clear_cache():
    global _cache_key, _cache_value
    _cache_key = _cache_value = None


CLASSES = (SPLINE_MAKER_OT_whole_selection,)
