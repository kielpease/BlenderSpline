"""Attach and detach curve paths and weld selected Bézier endpoints."""

import bpy

from . import edit_drag, lifecycle, region_selection, segment_selection, topology_edit


def editable_curve(obj):
    return (obj is not None and obj.type == "CURVE" and obj.is_editable and obj.data.is_editable
            and bool(obj.data.splines) and all(s.type == "BEZIER" for s in obj.data.splines))


def attached_geometry(source, matrix):
    return [
        [(matrix @ anchor, matrix @ left, matrix @ right, lt, rt)
         for anchor, left, right, lt, rt in (edit_drag.snapshot(p) for p in spline.bezier_points)]
        for spline in source.data.splines
    ]


def restore_attached_point(point, state):
    anchor, left, right, lt, rt = state
    # Join recalculates Auto handles in the destination's coordinates. Under
    # nonuniform transforms this can change the world-space curve shape.
    changed_left = (point.handle_left - left).length > 1e-6
    changed_right = (point.handle_right - right).length > 1e-6
    if lt == rt == "AUTO" and (changed_left or changed_right):
        lt = rt = "ALIGNED"
    else:
        if lt in {"AUTO", "VECTOR"} and changed_left:
            lt = "FREE"
        if rt in {"AUTO", "VECTOR"} and changed_right:
            rt = "FREE"
    edit_drag.restore(point, (anchor, left, right, lt, rt))


class SPLINE_MAKER_OT_attach_curves(bpy.types.Operator):
    bl_idname = "spline_maker.attach_curves"
    bl_label = "Attach Curves"
    bl_description = "Attach all selected Bézier curve objects to the active one, keeping their paths in place"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        if context.mode != "OBJECT" or context.area is None or context.area.type != "VIEW_3D":
            return False
        selected = context.selected_objects
        return (
            len(selected) >= 2 and context.active_object in selected
            and all(editable_curve(obj) for obj in selected)
            and not any(lifecycle.active_gestures()) and bpy.ops.object.join.poll()
        )

    def execute(self, context):
        from .profile import is_profile_modifier
        target = context.active_object
        # Native Join appends paths in selected_editable_objects order.
        selected = context.selected_editable_objects
        if len(selected) != len(context.selected_objects) or target not in selected:
            self.report({"WARNING"}, "All selected curves must be editable in this view layer")
            return {"CANCELLED"}
        sources = [obj for obj in selected if obj != target]
        if any(obj.data.shape_keys for obj in selected):
            self.report({"WARNING"}, "Attach requires curves without shape keys")
            return {"CANCELLED"}
        # Building this set once avoids a scan of all objects for each source.
        parents = {obj.parent for obj in bpy.data.objects if obj.parent is not None}
        for source in sources:
            has_modifiers = any(not is_profile_modifier(modifier) or modifier.show_viewport or modifier.show_render
                                for modifier in source.modifiers)
            if (source in parents or has_modifiers
                    or topology_edit.has_animation(source) or topology_edit.has_animation(source.data)):
                self.report({"WARNING"}, f"Attach source '{source.name}' has children, modifiers, or animation")
                return {"CANCELLED"}
        if any(abs(obj.matrix_world.determinant()) < 1e-12 for obj in selected):
            self.report({"WARNING"}, "Attach requires all selected curves to have nonzero scale")
            return {"CANCELLED"}

        original = target.data
        prior_dimensions = original.dimensions
        count = len(original.splines)
        inverse = target.matrix_world.inverted()
        geometry = [spline for source in sources
                    for spline in attached_geometry(source, inverse @ source.matrix_world)]
        if original.users > 1:
            target.data = original.copy()
        data = target.data
        if prior_dimensions == "2D" and any(abs(v.z) > 1e-6 for spline in geometry
                                            for state in spline for v in state[:3]):
            data.dimensions = "3D"
        try:
            result = bpy.ops.object.join()
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            result = {"CANCELLED"}
        if result != {"FINISHED"}:
            if data != original:
                target.data = original
                bpy.data.curves.remove(data)
            else:
                data.dimensions = prior_dimensions
            return result
        for spline, states in zip(data.splines[count:], geometry):
            for point, state in zip(spline.bezier_points, states):
                restore_attached_point(point, state)
        data.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


class SPLINE_MAKER_OT_detach_splines(bpy.types.Operator):
    bl_idname = "spline_maker.detach_splines"
    bl_label = "Detach"
    bl_description = "Move the selected paths to a new curve object, leaving at least one path on the original"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        if not topology_edit.context_ready(context) or segment_selection.level(context) != "REGION":
            return False
        obj = context.edit_object
        if not editable_curve(obj) or len(obj.data.splines) < 2 or not bpy.ops.curve.separate.poll():
            return False
        return 0 < len(region_selection.selected_regions(obj.data)) < len(obj.data.splines)

    def execute(self, context):
        obj = context.edit_object
        data = obj.data
        reason = topology_edit.unsupported_reason(obj, rebuilding=True)
        if not reason and data.users - int(data.use_fake_user) > 1:
            reason = "Make the curve data single-user before detaching its paths"
        if reason:
            self.report({"WARNING"}, reason)
            return {"CANCELLED"}

        # Separate reads native point flags. Clear any partial or edit-hidden
        # selection outside the complete paths selected in Spline mode.
        selected = region_selection.selected_regions(data)
        changed_flags = []
        for index, spline in enumerate(data.splines):
            if index in selected:
                continue
            for point in spline.bezier_points:
                state = (point.select_control_point, point.select_left_handle, point.select_right_handle)
                if any(state):
                    changed_flags.append((point, state))
                    point.select_control_point = point.select_left_handle = point.select_right_handle = False
        try:
            result = bpy.ops.curve.separate()
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            result = {"CANCELLED"}
        if result == {"FINISHED"}:
            context.area.tag_redraw()
        else:
            for point, state in changed_flags:
                point.select_control_point, point.select_left_handle, point.select_right_handle = state
        return result


def open_endpoint(spline, index):
    count = len(spline.bezier_points)
    return not spline.use_cyclic_u and count >= 2 and index in {0, count - 1}


def reverse_point(state):
    (anchor, left, right, lt, rt), radius, tilt, weight, hidden = state
    return (anchor, right, left, rt, lt), radius, -tilt, weight, hidden


def welded_point(incoming, outgoing):
    (a, left, _, _, _), radius_a, tilt_a, weight_a, _ = incoming
    (b, _, right, _, _), radius_b, tilt_b, weight_b, _ = outgoing
    center = (a + b) / 2
    geometry = (center, center + (left - a), center + (right - b), "FREE", "FREE")
    return geometry, (radius_a + radius_b) / 2, (tilt_a + tilt_b) / 2, (weight_a + weight_b) / 2, False


def path_states(spline, moved):
    points = spline.bezier_points
    # Moving the endpoint also changes its neighbor's automatic tangent.
    # Preserve that neighbor's control polygon on both incident spans.
    return [topology_edit.replacement_point(point, cut_left=i == 1 and 0 in moved,
                                           cut_right=i == len(points) - 2 and len(points) - 1 in moved)
            for i, point in enumerate(points)]


def weld_plan(spline, index, other, other_index, *, closing):
    moving = spline.bezier_points[index].co != other.bezier_points[other_index].co
    if closing:
        # Preserve the original direction and keep the first vertex at the seam.
        points = path_states(spline, {index, other_index} if moving else set())
        return [welded_point(points[-1], points[0]), *points[1:-1]], 0
    points = path_states(spline, {index} if moving else set())
    secondary = path_states(other, {other_index} if moving else set())
    if index == 0:
        if other_index == 0:
            secondary = [reverse_point(state) for state in reversed(secondary)]
        return [*secondary[:-1], welded_point(secondary[-1], points[0]), *points[1:]], len(secondary) - 1
    if other_index != 0:
        secondary = [reverse_point(state) for state in reversed(secondary)]
    return [*points[:-1], welded_point(points[-1], secondary[0]), *secondary[1:]], len(points) - 1


class SPLINE_MAKER_OT_weld_verts(bpy.types.Operator):
    bl_idname = "spline_maker.weld_verts"
    bl_label = "Weld Verts"
    bl_description = "Weld two selected open endpoints at their midpoint, keeping their connected handles"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return topology_edit.context_ready(context) and segment_selection.level(context) == "VERTEX"

    def execute(self, context):
        obj = context.edit_object
        reason = topology_edit.unsupported_reason(obj, rebuilding=True)
        if reason:
            self.report({"WARNING"}, reason)
            return {"CANCELLED"}
        data = obj.data
        keys = sorted(topology_edit.vertex_keys(data))
        if len(keys) != 2 or not all(open_endpoint(data.splines[si], pi) for si, pi in keys):
            self.report({"INFO"}, "Select exactly two endpoints on open Bézier paths")
            return {"CANCELLED"}
        (si, pi), (ti, qi) = keys
        primary, secondary = data.splines[si], data.splines[ti]
        closing = si == ti
        if closing and len(primary.bezier_points) < 3:
            self.report({"INFO"}, "Closing by weld requires at least three vertices before the weld")
            return {"CANCELLED"}
        points, seam = weld_plan(primary, pi, secondary, qi, closing=closing)
        selected = [i == seam for i in range(len(points))]
        try:
            topology_edit.replace_splines(data, {si, ti}, [
                (topology_edit.spline_properties(primary), points, selected, closing)
            ])
        except (RuntimeError, ValueError, TypeError) as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        context.area.tag_redraw()
        return {"FINISHED"}


CLASSES = (SPLINE_MAKER_OT_attach_curves, SPLINE_MAKER_OT_detach_splines, SPLINE_MAKER_OT_weld_verts)
