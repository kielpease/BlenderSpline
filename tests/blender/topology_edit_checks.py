"""Native path topology, handle preservation, and Undo/Redo regressions."""

import bpy

from insert_vertex_checks import create_curve
from lifecycle_checks import activate, geometry, viewport


def spans(spline):
    points = spline.bezier_points
    return [(points[i].co.copy(), points[i].handle_right.copy(), points[j].handle_left.copy(), points[j].co.copy())
            for i in range(len(points) if spline.use_cyclic_u else len(points) - 1)
            for j in ((i + 1) % len(points),)]


def run(module):
    seg = module.segment_selection
    manager = bpy.context.window_manager
    with viewport():
        for closed, count, level, selected, operator, expected in (
            (False, 4, "VERTEX", {1}, "remove_vert", [[0, 2, 3]]),
            (True, 4, "VERTEX", {1}, "delete_selection", [[0, 2, 3]]),
            (False, 4, "SEGMENT", {0, 2}, "remove_segment", [[0], [1, 2], [3]]),
            (True, 4, "SEGMENT", {3}, "delete_selection", [[0, 1, 2, 3]]),
            (True, 2, "SEGMENT", {1}, "remove_segment", [[0, 1]]),
            (True, 4, "SEGMENT", {0, 1, 2, 3}, "remove_segment", [[1], [2], [3], [0]]),
            (False, 4, "VERTEX", {1, 2}, "break_verts", [[0, 1], [1, 2], [2, 3]]),
            (True, 4, "VERTEX", {1}, "break_verts", [[1, 2, 3, 0, 1]]),
            (True, 2, "VERTEX", {0}, "break_verts", [[0, 1, 0]]),
        ):
            obj = create_curve(closed, count, ("AUTO", "ALIGNED", "VECTOR", "FREE")[:count])
            activate(obj)
            assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
            assert bpy.ops.spline_maker.enter_selection_level(target=level) == {"FINISHED"}
            first, other = obj.data.splines
            first.resolution_u = 26
            first.use_smooth = False
            first.radius_interpolation = "LINEAR"
            first.tilt_interpolation = "BSPLINE"
            bpy.context.view_layer.update()
            if level == "SEGMENT":
                seg.select(obj.data, {(0, i) for i in selected})
            else:
                for i, point in enumerate(first.bezier_points):
                    point.select_control_point = i in selected
                    point.select_right_handle = i not in selected
            untouched = geometry(obj)[1]
            anchors = [p.co.copy() for p in first.bezier_points]
            attributes = [(p.radius, p.tilt, p.weight_softbody) for p in first.bezier_points]
            originals = spans(first)
            before = geometry(obj)
            if operator == "break_verts" and not closed:
                for point in first.bezier_points:
                    point.select_control_point = False
                first.bezier_points[0].select_control_point = True
                assert bpy.ops.spline_maker.break_verts() == {"CANCELLED"}
                assert geometry(obj) == before
                for i, point in enumerate(first.bezier_points):
                    point.select_control_point = i in selected
            original_selection = [
                (p.select_control_point, p.select_left_handle, p.select_right_handle)
                for spline in obj.data.splines for p in spline.bezier_points
            ]
            assert bpy.ops.spline_maker.delete_selection.poll()
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
            assert not bpy.ops.spline_maker.delete_selection.poll()
            assert bpy.ops.spline_maker.switch_tangent_tool(target="SELECT") == {"FINISHED"}
            assert bpy.ops.ed.undo_push(message="Before topology edit") == {"FINISHED"}

            assert getattr(bpy.ops.spline_maker, operator)("EXEC_DEFAULT", True) == {"FINISHED"}
            assert bpy.context.mode == "EDIT_CURVE"
            bpy.context.view_layer.update()
            assert other in list(obj.data.splines)
            edited = geometry(obj)
            assert edited[list(obj.data.splines).index(other)] == untouched
            assert all(p.hide for p in other.bezier_points)
            paths = [spline for spline in obj.data.splines if spline != other]
            assert len(paths) == len(expected)
            for spline, indices in zip(paths, expected):
                assert [p.co for p in spline.bezier_points] == [anchors[i] for i in indices]
                actual = [(p.radius, p.tilt, p.weight_softbody) for p in spline.bezier_points]
                assert actual == [attributes[i] for i in indices], (operator, indices, actual, attributes)
                assert spline.resolution_u == 26 and not spline.use_smooth
                assert spline.radius_interpolation == "LINEAR" and spline.tilt_interpolation == "BSPLINE"
                if operator == "break_verts" or level == "SEGMENT":
                    assert not spline.use_cyclic_u
                    for actual, index in zip(spans(spline), indices):
                        assert all((a - b).length < 2e-5 for a, b in zip(actual, originals[index]))
                    projected = list(module.vertex_selection.project_components(
                        spline, obj.matrix_world, lambda p: (p.x, p.y), "ALL"
                    ))
                    assert not any(c.coordinate == "handle_left" and c.point == spline.bezier_points[0]
                                   for c in projected)
                    assert not any(c.coordinate == "handle_right" and c.point == spline.bezier_points[-1]
                                   for c in projected)
                if operator == "break_verts":
                    assert [p.select_control_point for p in spline.bezier_points] == [i in selected for i in indices]
            assert manager.spline_maker_selection_level == level
            assert bpy.ops.ed.undo() == {"FINISHED"}
            assert bpy.context.mode == "EDIT_CURVE" and geometry(bpy.context.edit_object) == before
            assert [(p.select_control_point, p.select_left_handle, p.select_right_handle)
                    for spline in bpy.context.edit_object.data.splines for p in spline.bezier_points] == original_selection
            assert bpy.ops.ed.redo() == {"FINISHED"}
            assert geometry(bpy.context.edit_object) == edited
            assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
            assert geometry(bpy.context.object) == edited

        obj = create_curve(False, 4, ("FREE",) * 4)
        activate(obj)
        obj.data.animation_data_create()
        assert not module.topology_edit.unsupported_reason(obj, rebuilding=True)
        obj.data.driver_add("bevel_depth")
        assert module.topology_edit.unsupported_reason(obj, rebuilding=True)
        assert not module.topology_edit.unsupported_reason(obj, rebuilding=False)
        obj.data.driver_remove("bevel_depth")
        obj.shape_key_add(name="Basis")
        assert module.topology_edit.unsupported_reason(obj, rebuilding=False)
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        obj.data.splines[0].bezier_points[1].select_control_point = True
        before = geometry(obj)
        assert bpy.ops.spline_maker.break_verts() == {"CANCELLED"}
        assert bpy.ops.spline_maker.remove_vert() == {"CANCELLED"}
        assert geometry(obj) == before
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    print("M6 removals and breaks preserve intended paths, attributes, and one-step Undo/Redo")
