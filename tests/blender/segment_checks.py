"""SM-011 checks on native data, with deterministic screen projection."""

from math import radians
import bpy
from mathutils import Matrix, Vector


def run(module):
    seg = module.segment_selection
    bounds = (0, 10, 0, 10)
    for a, b, expected in (
        ((-5, 5), (15, 5), True),  # Both endpoints outside; edge crosses.
        ((5, -5), (5, 15), True),
        ((-1, 1), (1, -1), True),  # Touches only a corner.
        ((-5, 0), (15, 0), True),  # Coincident with a box edge.
        ((-2, 9), (9, 20), False),  # Bounding boxes overlap, but the edge misses.
        ((-5, -1), (15, -1), False),
        ((5, 5), (5, 5), True),
        ((15, 5), (15, 5), False),
    ):
        assert seg.edge_intersects_box(a, b, bounds) == expected
        assert seg.edge_intersects_box(b, a, bounds) == expected
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.spline_maker.add_test_curve()
        obj = bpy.context.object
        points = obj.data.splines[0].bezier_points
        points.add(3)
        for i, point in enumerate(points):
            point.co = (3 * i, 0, 0)
            point.handle_left_type = point.handle_right_type = "FREE"
            point.handle_left = (3 * i - 0.8, 2, 0)
            point.handle_right = (3 * i + 0.8, 2, 0)
        other = obj.data.splines.new("BEZIER")
        other.bezier_points.add(1)
        for point, x in zip(other.bezier_points, (0, 4)):
            point.co = (x, -6, 0)
            point.handle_left_type = point.handle_right_type = "VECTOR"
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            bpy.ops.spline_maker.switch_tangent_tool(target="SELECT")
            bpy.ops.spline_maker.selection_level(target="SEGMENT")
            data = obj.data
            points = data.splines[0].bezier_points
            assert not seg.selected(data)
            assert len(list(seg.segments(data))) == 5
            matrix = Matrix.Translation((4, -3, 1)) @ Matrix.Rotation(radians(28), 4, "Z") @ Matrix.Diagonal((1.7, 0.6, 2, 1))
            for zoom in (12, 80, 350):
                project = lambda p: (500 + zoom * p.x, 350 + zoom * p.y)
                projected = seg.projected_segments(data, matrix, project)
                midpoint = project(matrix @ Vector((1.5, 1.5, 0)))
                assert seg.pick(projected, midpoint) == (0, 0)
                assert seg.pick(projected, project(matrix @ Vector((2, -6, 0)))) == (1, 0)
                assert seg.pick(projected, (-10000, -10000)) is None
                assert len(projected[0][1]) > 2
                seg.click(data, projected, midpoint, extend=False)
                assert seg.selected(data) == {(0, 0)}
                seg.click(data, projected, midpoint, extend=True)
                assert seg.selected(data) == set()
                seg.select(data, {(0, 2)})
                seg.click(data, projected, midpoint, extend=True)
                assert seg.selected(data) == {(0, 0), (0, 2)}
                # All four anchors are selected, but the connecting middle edge isn't.
                assert all(points[i].select_control_point for i in range(4))
                assert (0, 1) not in seg.selected(data)
                # A tiny box around the curved middle selects the full segment,
                # without enclosing either control-point anchor.
                lo = (midpoint[0] - 3, midpoint[1] - 3)
                hi = (midpoint[0] + 3, midpoint[1] + 3)
                seg.box(data, projected, lo, hi, extend=False)
                assert seg.selected(data) == {(0, 0)}
                seg.box(data, projected, hi, lo, extend=False)
                assert seg.selected(data) == {(0, 0)}
                seg.select(data, {(0, 2)})
                seg.box(data, projected, hi, lo, extend=True)
                assert seg.selected(data) == {(0, 0), (0, 2)}
                seg.box(data, projected, lo, hi, extend=False)
                seg.click(data, projected, (-10000, -10000), extend=True)
                assert seg.selected(data) == {(0, 0)}
                seg.click(data, projected, (-10000, -10000), extend=False)
                assert not seg.selected(data)

            # Sparse sampled edges must select on crossing even if neither
            # sample endpoint lies inside. Nearby misses must stay unselected.
            sparse = [((0, 0), [((-20, 5), (20, 5))]),
                      ((0, 2), [((-2, 9), (9, 20))]), ((0, 3), [])]
            seg.box(data, sparse, (0, 0), (10, 10), extend=False)
            assert seg.selected(data) == {(0, 0)}
            seg.box(data, sparse, (10, 10), (0, 0), extend=False)
            assert seg.selected(data) == {(0, 0)}
            seg.box(data, sparse, (30, 30), (40, 40), extend=True)
            assert seg.selected(data) == {(0, 0)}
            seg.box(data, sparse, (30, 30), (40, 40), extend=False)
            assert not seg.selected(data)

            seg.select(data, {(0, 0), (0, 1)})
            assert seg.endpoints(data, seg.selected(data)) == {(0, 0), (0, 1), (0, 2)}
            anchors = module.edit_drag.selected_anchors(bpy.context)
            assert len(anchors) == 3 and len({p.as_pointer() for p in anchors}) == 3
            before = [module.edit_drag.snapshot(p) for p in points]
            for point in anchors:
                module.edit_drag.translate_anchor(point, module.edit_drag.snapshot(point), Vector((1, 2, 0)))
            assert all(points[i].co == before[i][0] + Vector((1, 2, 0)) for i in range(3))
            assert points[3].co == before[3][0]
            assert seg.selected(data) == {(0, 0), (0, 1)}
            for p, state in zip(points, before):
                module.edit_drag.restore(p, state)
            for target in ("MOVE", "ROTATE", "SCALE", "SELECT"):
                bpy.ops.spline_maker.switch_tangent_tool(target=target)
                assert seg.selected(data) == {(0, 0), (0, 1)}
                if target in {"ROTATE", "SCALE"}:
                    assert not bpy.ops.spline_maker.tangent_drag.poll()
                    assert not bpy.ops.spline_maker.tangent_step.poll()

            data.splines[0].use_cyclic_u = True
            assert len(list(seg.segments(data))) == 6
            seg.select(data, {(0, 4)})
            assert seg.selected(data) == {(0, 4)}
            assert seg.endpoints(data, seg.selected(data)) == {(0, 4), (0, 0)}
            points[0].hide = True
            assert not seg.selected(data)
            assert len(list(seg.segments(data))) == 4
            seg.box(data, [((0, 4), [((0, 0), (10, 10))])], (2, 2), (8, 8), extend=False)
            assert not seg.selected(data)
            points[0].hide = False

            # Direct handle editing must leave the segment-code flags untouched.
            seg.select(data, {(0, 0), (0, 2)})
            module.edit_drag.translate_handle(points[1], module.edit_drag.snapshot(points[1]),
                                              "handle_right", Vector((0, 0.5, 0)))
            assert seg.selected(data) == {(0, 0), (0, 2)}
            bpy.ops.spline_maker.selection_level(target="VERTEX")
            assert not seg.is_active(bpy.context)
            assert all(points[i].select_control_point for i in range(4))
            bpy.ops.spline_maker.selection_level(target="SEGMENT")
            assert not seg.selected(data)
            # Entirely unprojectable curves cannot become phantom pick edges.
            assert not seg.curve_edges(tuple(p.co for p in points[:4]), lambda _: None)
            assert seg.distance_squared((5, 2), (0, 0), (10, 0)) == 4
            assert seg.distance_squared((2, 0), (0, 0), (0, 0)) == 4
            # Native Edit Mode Undo must retain the individual edge codes,
            # rather than reconstructing them from anchor selection alone.
            seg.select(data, {(0, 0)})
            bpy.ops.ed.undo_push(message="SM-011 first segment")
            seg.select(data, {(0, 2)})
            bpy.ops.ed.undo_push(message="SM-011 second segment")
            if bpy.ops.ed.undo.poll():
                assert bpy.ops.ed.undo() == {"FINISHED"}
                assert seg.selected(bpy.context.edit_object.data) == {(0, 0)}
                assert bpy.ops.ed.redo() == {"FINISHED"}
                assert seg.selected(bpy.context.edit_object.data) == {(0, 2)}
                print("SM-011 native Edit Mode selection undo/redo passed")
            else:
                print("SM-011 native selection undo/redo needs UI testing (background poll unavailable)")
        finally:
            bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
            bpy.ops.object.mode_set(mode="OBJECT")
