# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""Remove anchors or segments, and break a path at its anchors."""

import bpy

from . import edit_drag, lifecycle, segment_selection
from .feasibility import active_mode
from .vertex_selection import supported_curve


_SPLINE_PROPERTIES = ("material_index", "radius_interpolation", "resolution_u",
                      "tilt_interpolation", "use_smooth")


def removed_segment_paths(count, cyclic, removed):
    first = (min(removed) + 1) % count if cyclic else 0
    path = []
    for index in range(first, first + count):
        index %= count
        path.append(index)
        if index in removed:
            yield path
            path = []
    if path:
        yield path


def broken_vertex_paths(count, cyclic, breaks):
    boundaries = sorted(breaks)
    if cyclic:
        boundaries.append(boundaries[0] + count)
    else:
        boundaries = [0, *boundaries, count - 1]
    for start, end in zip(boundaries, boundaries[1:]):
        yield [index % count for index in range(start, end + 1)]


def vertex_keys(data, *, interior=False):
    return {(si, pi) for si, spline in enumerate(data.splines)
            for pi, point in enumerate(spline.bezier_points)
            if point.select_control_point and not point.hide
            and (not interior or (len(spline.bezier_points) > 1
                 and (spline.use_cyclic_u or 0 < pi < len(spline.bezier_points) - 1)))}


def context_ready(context):
    return (context.area is not None and context.area.type == "VIEW_3D"
            and supported_curve(context) and active_mode(context) is not None
            and not any(lifecycle.active_gestures()))


def has_animation(data):
    animation = data.animation_data
    return animation is not None and bool(animation.action or animation.drivers or animation.nla_tracks)


def unsupported_reason(obj, *, rebuilding):
    data = obj.data
    if data.shape_keys:
        return "Topology edits require a curve without shape keys"
    if rebuilding and (has_animation(data) or any(mod.type == "HOOK" for mod in obj.modifiers)):
        return "Rebuilding paths requires a curve without curve-data animation or Hook modifiers"
    if rebuilding and data.users > 1:
        for other in bpy.data.objects:
            if other.data == data and any(mod.type == "HOOK" for mod in other.modifiers):
                return "A linked object uses Hook modifiers for this curve"
    return ""


def remove_vertices(context):
    data = context.edit_object.data
    targets = vertex_keys(data)
    if not targets or not bpy.ops.curve.delete.poll():
        return {"CANCELLED"}
    flags = []
    for si, spline in enumerate(data.splines):
        for pi, point in enumerate(spline.bezier_points):
            flags.append((point, point.select_control_point, point.select_left_handle, point.select_right_handle))
            point.select_control_point = (si, pi) in targets
            point.select_left_handle = point.select_right_handle = False
    result = bpy.ops.curve.delete(type="VERT")
    if result != {"FINISHED"}:
        for point, anchor, left, right in flags:
            point.select_control_point, point.select_left_handle, point.select_right_handle = anchor, left, right
    return result


def spline_properties(spline):
    return tuple(getattr(spline, name) for name in _SPLINE_PROPERTIES)


def replacement_point(point, *, cut_left=False, cut_right=False):
    anchor, left, right, left_type, right_type = edit_drag.snapshot(point)
    if cut_left or cut_right:
        # A new endpoint has lost a neighbor. Freeze automatic tangents so
        # Blender keeps the original control polygon on the surviving span.
        if left_type == "AUTO" or (cut_left and left_type == "VECTOR"):
            left_type = "FREE"
        if right_type == "AUTO" or (cut_right and right_type == "VECTOR"):
            right_type = "FREE"
    return ((anchor, left, right, left_type, right_type), point.radius, point.tilt,
            point.weight_softbody, point.hide)


def replace_paths(data, keys, *, breaking):
    grouped = {}
    for si, index in keys:
        grouped.setdefault(si, set()).add(index)
    plans = []
    for si, cuts in sorted(grouped.items()):
        spline = data.splines[si]
        points = spline.bezier_points
        count, cyclic = len(points), spline.use_cyclic_u
        properties = spline_properties(spline)
        paths = broken_vertex_paths(count, cyclic, cuts) if breaking else removed_segment_paths(count, cyclic, cuts)
        for path in paths:
            states = [
                replacement_point(points[index], cut_left=i == 0 and (cyclic or index > 0),
                                  cut_right=i == len(path) - 1 and (cyclic or index < count - 1))
                for i, index in enumerate(path)
            ]
            plans.append((properties, states, [breaking and index in cuts for index in path], False))
    replace_splines(data, grouped, plans)


def replace_splines(data, source_indices, plans):
    if not bpy.ops.curve.delete.poll():
        raise RuntimeError("Blender's curve deletion operator is unavailable")
    previous_active = data.splines.active
    replacements = []
    try:
        for properties, states, selection, cyclic in plans:
            spline = data.splines.new("BEZIER")
            replacements.append(spline)
            for name, value in zip(_SPLINE_PROPERTIES, properties):
                setattr(spline, name, value)
            spline.bezier_points.add(len(states) - 1)
            spline.use_cyclic_u = cyclic
            for point, (geometry, radius, tilt, weight, hidden), selected in zip(spline.bezier_points, states, selection):
                edit_drag.restore(point, geometry)
                point.radius, point.tilt = radius, tilt
                if point.weight_softbody != weight:
                    point.weight_softbody = weight
                point.hide = hidden
                point.select_control_point = selected
                point.select_left_handle = point.select_right_handle = False
    except (RuntimeError, ValueError, TypeError):
        for replacement in reversed(replacements):
            data.splines.remove(replacement)
        raise

    # Native deletion removes edit-curve bookkeeping for the old control
    # points. Temporarily select just those paths, including their hidden points.
    retained, removed = [], []
    replace_active = previous_active is None
    for si, spline in enumerate(data.splines):
        deleting = si in source_indices
        if deleting and spline == previous_active:
            replace_active = True
        for point in spline.bezier_points:
            state = (point, point.hide, point.select_control_point,
                     point.select_left_handle, point.select_right_handle)
            (removed if deleting else retained).append(state)
            if deleting:
                point.hide = False
            point.select_control_point = deleting
            point.select_left_handle = point.select_right_handle = False
    result = bpy.ops.curve.delete(type="VERT")
    for point, hidden, anchor, left, right in retained:
        point.select_control_point, point.select_left_handle, point.select_right_handle = anchor, left, right
    if result != {"FINISHED"}:
        for point, hidden, anchor, left, right in removed:
            point.hide = hidden
            point.select_control_point, point.select_left_handle, point.select_right_handle = anchor, left, right
        for replacement in reversed(replacements):
            data.splines.remove(replacement)
        data.splines.active = previous_active
        raise RuntimeError("Blender could not replace the selected paths")
    if replace_active:
        data.splines.active = replacements[0]
    else:
        data.splines.active = previous_active
    data.update_tag()


def execute_edit(operator, context, action):
    obj = context.edit_object
    reason = unsupported_reason(obj, rebuilding=action != "REMOVE_VERT")
    if reason:
        operator.report({"WARNING"}, reason)
        return {"CANCELLED"}
    if action == "REMOVE_VERT":
        result = remove_vertices(context)
        if result != {"FINISHED"}:
            operator.report({"INFO"}, "Select one or more vertices")
            return result
    else:
        breaking = action == "BREAK_VERTS"
        keys = vertex_keys(obj.data, interior=True) if breaking else segment_selection.selected(obj.data)
        if not keys:
            operator.report({"INFO"}, "Select an interior vertex or a closed-loop vertex"
                            if breaking else "Select one or more segments")
            return {"CANCELLED"}
        try:
            replace_paths(obj.data, keys, breaking=breaking)
        except (RuntimeError, ValueError, TypeError) as exc:
            operator.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
    obj.data.update_tag()
    context.area.tag_redraw()
    return {"FINISHED"}


class SPLINE_MAKER_OT_remove_vert(bpy.types.Operator):
    bl_idname = "spline_maker.remove_vert"
    bl_label = "Remove Vert"
    bl_description = "Remove selected vertices and reconnect their neighbors (Delete in Vertex mode)"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context_ready(context) and segment_selection.level(context) == "VERTEX"

    def execute(self, context):
        return execute_edit(self, context, "REMOVE_VERT")


class SPLINE_MAKER_OT_remove_segment(bpy.types.Operator):
    bl_idname = "spline_maker.remove_segment"
    bl_label = "Remove Segment"
    bl_description = "Remove selected segments and leave their endpoint vertices (Delete in Segment mode)"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context_ready(context) and segment_selection.level(context) == "SEGMENT"

    def execute(self, context):
        return execute_edit(self, context, "REMOVE_SEGMENT")


class SPLINE_MAKER_OT_break_verts(bpy.types.Operator):
    bl_idname = "spline_maker.break_verts"
    bl_label = "Break Verts"
    bl_description = "Split at selected vertices, leaving coincident endpoints and preserving the adjoining spans"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context_ready(context) and segment_selection.level(context) == "VERTEX"

    def execute(self, context):
        return execute_edit(self, context, "BREAK_VERTS")


class SPLINE_MAKER_OT_delete_selection(bpy.types.Operator):
    bl_idname = "spline_maker.delete_selection"
    bl_label = "Delete Spline Selection"
    bl_description = "Remove vertices or segments at the active Spline selection level"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context_ready(context) and segment_selection.level(context) in {"VERTEX", "SEGMENT"}

    def execute(self, context):
        action = "REMOVE_VERT" if segment_selection.level(context) == "VERTEX" else "REMOVE_SEGMENT"
        return execute_edit(self, context, action)


CLASSES = (
    SPLINE_MAKER_OT_remove_vert, SPLINE_MAKER_OT_remove_segment, SPLINE_MAKER_OT_break_verts,
    SPLINE_MAKER_OT_delete_selection,
)
