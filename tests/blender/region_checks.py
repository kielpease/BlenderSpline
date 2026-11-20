"""SM-012 native selection, region validation, projection, and undo checks."""

from types import SimpleNamespace
import bpy
from mathutils import Matrix, Quaternion, Vector


def run(module):
    region = module.region_selection
    geometry = __import__(module.__name__ + ".region_geometry", fromlist=["validate"])
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    window_region = next(r for r in area.regions if r.type == "WINDOW")

    def add_loop(data, coords, closed=True):
        spline = data.splines.new("BEZIER")
        spline.bezier_points.add(len(coords) - 1)
        spline.use_cyclic_u = closed
        for point, co in zip(spline.bezier_points, coords):
            point.co = co
            point.handle_left_type = point.handle_right_type = "FREE"
            point.handle_left = point.handle_right = point.co
        return spline

    square = [(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0)]
    with bpy.context.temp_override(area=area, region=window_region):
        data = bpy.data.curves.new("Region checks", "CURVE")
        data.dimensions = "3D"
        add_loop(data, square)
        add_loop(data, [(x + 8, y, z) for x, y, z in square])
        add_loop(data, [(0, -4, 0), (3, -4, 0)], closed=False)
        obj = bpy.data.objects.new("Region checks", data)
        bpy.context.collection.objects.link(obj)
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
            assert not bpy.ops.spline_maker.selection_level.poll()
            assert bpy.ops.spline_maker.enter_selection_level.poll()
            assert bpy.ops.spline_maker.enter_selection_level(target="SEGMENT") == {"FINISHED"}
            assert module.feasibility.active_mode(bpy.context) == "SELECT"
            assert module.segment_selection.level(bpy.context) == "SEGMENT"
            bpy.ops.wm.tool_set_by_id(name="builtin.move")
            assert bpy.ops.spline_maker.enter_selection_level(target="REGION") == {"FINISHED"}
            assert module.feasibility.active_mode(bpy.context) == "SELECT"
            assert module.segment_selection.level(bpy.context) == "REGION"
            bpy.ops.spline_maker.switch_tangent_tool(target="SELECT")
            data = obj.data
            assert set(region.regions(data)[0]) == {0, 1}
            assert not region.unavailable_reason(data)
            bpy.ops.spline_maker.selection_level(target="REGION")
            assert not region.selected_regions(data)
            region.select_regions(data, {0})
            assert region.selected_regions(data) == {0}
            assert len(module.edit_drag.selected_anchors(bpy.context)) == 4
            assert module.feasibility.move_origin(bpy.context) == Vector((2, 2, 0))
            region.select_regions(data, {0, 1})
            assert len(module.edit_drag.selected_anchors(bpy.context)) == 8
            before = [p.co.copy() for s in data.splines for p in s.bezier_points]
            active = bpy.context.view_layer.objects.active
            bpy.ops.spline_maker.selection_level(target="WHOLE")
            assert region.whole_selected(data)
            assert active == bpy.context.view_layer.objects.active and obj.select_get()
            assert len(module.edit_drag.selected_anchors(bpy.context)) == 10
            for target in ("MOVE", "ROTATE", "SCALE"):
                bpy.ops.spline_maker.switch_tangent_tool(target=target)
                assert bpy.ops.spline_maker.move_drag.poll() == (target == "MOVE")
                assert bpy.ops.spline_maker.tangent_drag.poll() == (target in {"ROTATE", "SCALE"})
            bpy.ops.spline_maker.whole_selection(action="CLEAR")
            assert not region.whole_selected(data) and obj.select_get()
            bpy.ops.spline_maker.whole_selection(action="SELECT")
            assert region.whole_selected(data)
            assert before == [p.co for s in data.splines for p in s.bezier_points]
            bpy.ops.spline_maker.selection_level(target="VERTEX")
            assert all(p.select_control_point for s in data.splines for p in s.bezier_points)
            bpy.ops.spline_maker.selection_level(target="REGION")

            # Real projection helpers, synthetic viewport: test interior clicks,
            # Shift toggles, complete-loop boxes and active-object invariance.
            fake = SimpleNamespace(edit_object=obj, window_manager=bpy.context.window_manager,
                region=SimpleNamespace(width=1000, height=700),
                region_data=SimpleNamespace(view_rotation=Quaternion(),
                    view_matrix=Matrix.Translation((0, 0, -10)),
                    perspective_matrix=Matrix.Diagonal((0.1, 0.1, -0.01, 1)),
                    is_perspective=False, view_perspective="ORTHO"))
            assert not region.click(fake, (600, 420), extend=False)  # local (2,2)
            assert region.selected_regions(data) == {0}
            assert not region.click(fake, (1000, 420), extend=True)  # local (10,2)
            assert region.selected_regions(data) == {0, 1}
            assert not region.click(fake, (600, 420), extend=True)
            assert region.selected_regions(data) == {1}
            region.box(fake, (490, 340), (710, 500), extend=False)
            assert region.selected_regions(data) == {0}
            region.click(fake, (100, 100), extend=False)
            assert not region.selected_regions(data)
            # An open path is a selectable spline, independently of closed loops.
            assert not region.click(fake, (575, 210), extend=False)
            assert region.selected_regions(data) == {2}
            assert len(module.edit_drag.selected_anchors(bpy.context)) == 2
            assert module.feasibility.move_origin(bpy.context) == Vector((1.5, -4, 0))
            assert region.outline_keys(fake) == {(2, 0)}
            assert not region.click(fake, (600, 420), extend=True)
            assert region.selected_regions(data) == {0, 2}
            assert not region.box(fake, (490, 200), (660, 220), extend=False)
            assert region.selected_regions(data) == {2}
            assert not region.box(fake, (490, 340), (710, 500), extend=True)
            assert region.selected_regions(data) == {0, 2}
            # Box selection needs the complete spline, not one enclosed endpoint.
            assert not region.box(fake, (490, 200), (540, 220), extend=False)
            assert not region.selected_regions(data)
            # Inverse/normal handling on an arbitrary nonuniform transform.
            obj.matrix_world = (Matrix.Translation((1, -1, 0)) @ Matrix.Rotation(0.4, 4, "Z")
                                @ Matrix.Rotation(0.5, 4, "X") @ Matrix.Diagonal((1.2, 0.8, 2, 1)))
            bpy.context.view_layer.update()
            hit = obj.matrix_world @ Vector((2, 2, 0))
            assert region.region_hits(fake, (500 + 50 * hit.x, 350 + 35 * hit.y))[0] == {0}
            obj.matrix_world = Matrix.Identity(4)
            bpy.context.view_layer.update()

            # Local geometry changes invalidate the validation cache.
            p = data.splines[0].bezier_points[0]
            old_handle = p.handle_right.copy()
            p.handle_right.z = 1
            assert not region.regions(data)[0]
            assert not region.unavailable_reason(data)
            assert bpy.ops.spline_maker.selection_level(target="REGION") == {"FINISHED"}
            assert not region.click(fake, (500, 350), extend=False)
            assert region.selected_regions(data) == {0}
            p.handle_right = old_handle
            assert set(region.regions(data)[0]) == {0, 1}
            # Separate planes can overlap on screen. Preserve selection and
            # report ambiguity rather than guessing front/back ownership.
            second = data.splines[1]
            states = [module.edit_drag.snapshot(p) for p in second.bezier_points]
            for p, state in zip(second.bezier_points, states):
                module.edit_drag.translate_anchor(p, state, Vector((-8, 0, 2)))
            region.select_regions(data, {0})
            assert set(region.regions(data)[0]) == {0, 1}
            assert "Multiple splines" in region.click(fake, (600, 420), extend=False)
            assert region.selected_regions(data) == {0}
            for p, state in zip(second.bezier_points, states):
                module.edit_drag.restore(p, state)
            region.select_regions(data, {0})
            bpy.ops.ed.undo_push(message="SM-012 first region")
            region.select_regions(data, {1})
            bpy.ops.ed.undo_push(message="SM-012 second region")
            assert bpy.ops.ed.undo() == {"FINISHED"}
            assert region.selected_regions(bpy.context.edit_object.data) == {0}
            assert bpy.ops.ed.redo() == {"FINISHED"}
            assert region.selected_regions(bpy.context.edit_object.data) == {1}
            print("SM-012 native region selection undo/redo passed")
            bpy.ops.spline_maker.selection_level(target="WHOLE")
            bpy.ops.ed.undo_push(message="SM-012 whole geometry selected")
            bpy.ops.spline_maker.whole_selection(action="CLEAR")
            bpy.ops.ed.undo_push(message="SM-012 whole geometry cleared")
            assert bpy.ops.ed.undo() == {"FINISHED"}
            assert region.whole_selected(bpy.context.edit_object.data)
            assert bpy.ops.ed.redo() == {"FINISHED"}
            assert not region.whole_selected(bpy.context.edit_object.data)
            assert bpy.context.edit_object == bpy.context.view_layer.objects.active
            print("SM-012 native whole-geometry selection undo/redo passed")
        finally:
            bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
            bpy.ops.object.mode_set(mode="OBJECT")
            assert not bpy.ops.spline_maker.enter_selection_level.poll()

    # Unsupported geometry is diagnosed, rather than inferred as a region.
    examples = [
        (square, False, "Open"),
        ([(0, 0, 0), (4, 4, 0), (0, 4, 0), (4, 0, 0)], True, "intersect"),
        ([(0, 0, 0), (2, 0, 0), (4, 0, 0)], True, "Collinear"),
        ([(0, 0, 0), (4, 0, 0), (4, 4, 1), (0, 4, 0)], True, "Nonplanar"),
    ]
    for coords, closed, reason in examples:
        test_data = bpy.data.curves.new("Unsupported region", "CURVE")
        add_loop(test_data, coords, closed)
        loops, reasons = geometry.validate(test_data)
        assert not loops and any(reason in message for message in reasons), reasons
        bpy.data.curves.remove(test_data)
    for offset, size in ((2, 4), (1, 1), (4, 4)):  # overlap, nested, touching
        test_data = bpy.data.curves.new("Ambiguous regions", "CURVE")
        add_loop(test_data, square)
        add_loop(test_data, [(offset, offset, 0), (offset + size, offset, 0),
                             (offset + size, offset + size, 0), (offset, offset + size, 0)])
        loops, reasons = geometry.validate(test_data)
        assert not loops and any("nested" in message for message in reasons), reasons
        bpy.data.curves.remove(test_data)
    test_data = bpy.data.curves.new("Curved region", "CURVE")
    circle = add_loop(test_data, [(3, 0, 0), (0, 3, 0), (-3, 0, 0), (0, -3, 0)])
    for point in circle.bezier_points:
        tangent = Vector((-point.co.y, point.co.x, 0)) * 0.55228475
        point.handle_left = point.co - tangent
        point.handle_right = point.co + tangent
    loops, reasons = geometry.validate(test_data)
    assert set(loops) == {0}, reasons
    assert len(loops[0].polygon) > 20
    assert geometry.inside(loops[0].uv(Vector((0, 0, 0))), loops[0].polygon)
    bpy.data.curves.remove(test_data)
    check_single_spline_entry(module, area, window_region)


def check_single_spline_entry(module, area, window_region):
    region = module.region_selection
    examples = (
        ([(0, 0, 0), (3, 0, 0), (3, 2, 0)], False),
        ([(0, 0, 0), (3, 0, 0), (3, 2, 0)], True),
        ([(0, 0, 0), (3, 0, 0), (3, 2, 1)], True),
        ([(0, 0, 0), (3, 2, 0), (0, 2, 0), (3, 0, 0)], True),
        ([(1, 2, 0)], False),
    )
    with bpy.context.temp_override(area=area, region=window_region):
        for index, (coords, closed) in enumerate(examples):
            bpy.ops.object.select_all(action="DESELECT")
            data = bpy.data.curves.new("Single spline entry", "CURVE")
            data.dimensions = "3D"
            spline = data.splines.new("BEZIER")
            spline.bezier_points.add(len(coords) - 1)
            spline.use_cyclic_u = closed
            for p, co in zip(spline.bezier_points, coords):
                p.co = co
                p.handle_left_type = p.handle_right_type = "FREE"
                p.handle_left = p.handle_right = p.co
            obj = bpy.data.objects.new("Single spline entry", data)
            bpy.context.collection.objects.link(obj)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            try:
                bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
                bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
                bpy.ops.curve.select_all(action="DESELECT")
                before = [module.edit_drag.snapshot(p) for p in obj.data.splines[0].bezier_points]
                if index == 0:
                    bpy.ops.ed.undo_push(message="Before single spline selection")
                assert bpy.ops.spline_maker.enter_selection_level(target="REGION") == {"FINISHED"}
                assert module.feasibility.active_mode(bpy.context) == "SELECT"
                assert region.selected_regions(obj.data) == {0}
                assert len(module.edit_drag.selected_anchors(bpy.context)) == len(coords)
                if index == 0:
                    bpy.ops.ed.undo_push(message="Single spline selected")
                    assert bpy.ops.ed.undo() == {"FINISHED"}
                    assert not region.selected_regions(bpy.context.edit_object.data)
                    assert bpy.ops.ed.redo() == {"FINISHED"}
                    obj = bpy.context.edit_object
                    assert region.selected_regions(obj.data) == {0}
                region.select_regions(obj.data, set())
                assert bpy.ops.spline_maker.selection_level(target="REGION") == {"FINISHED"}
                assert region.selected_regions(obj.data) == {0}  # Repeating 3 reselects.
                bpy.ops.spline_maker.selection_level(target="VERTEX")
                assert all(p.select_control_point for p in obj.data.splines[0].bezier_points)
                bpy.ops.spline_maker.selection_level(target="REGION")
                assert region.selected_regions(obj.data) == {0}
                assert [module.edit_drag.snapshot(p) for p in obj.data.splines[0].bezier_points] == before
                # Hidden vertices prevent partial-spline transforms.
                bpy.ops.spline_maker.selection_level(target="VERTEX")
                obj.data.splines[0].bezier_points[0].hide = True
                flags = [(p.select_control_point, p.select_left_handle, p.select_right_handle)
                         for p in obj.data.splines[0].bezier_points]
                assert bpy.ops.spline_maker.selection_level(target="REGION") == {"CANCELLED"}
                assert [(p.select_control_point, p.select_left_handle, p.select_right_handle)
                        for p in obj.data.splines[0].bezier_points] == flags
                obj.data.splines[0].bezier_points[0].hide = False
                extra = obj.data.splines.new("BEZIER")
                extra.bezier_points[0].hide = True
                assert bpy.ops.spline_maker.selection_level(target="REGION") == {"FINISHED"}
                assert not region.selected_regions(obj.data)  # Multiple paths: no arbitrary auto-pick.
            finally:
                bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
                bpy.ops.object.mode_set(mode="OBJECT")
        print("Spline-level auto-selection, open-path picking, hidden guards and native undo passed")
