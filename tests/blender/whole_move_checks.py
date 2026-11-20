"""SM-014 complete-curve Move, using native data and synthetic drag events."""

from types import SimpleNamespace

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Euler, Matrix, Vector


def run(module):
    drag = module.edit_drag
    cls = drag.SPLINE_MAKER_OT_move_drag
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.object.select_all(action="DESELECT")
        data = bpy.data.curves.new("Whole Move checks", "CURVE")
        data.dimensions = "3D"
        for coords, types in (
            (((-2, -1, 0), (0, 2, 0), (3, 0, 0)), ("FREE", "ALIGNED", "AUTO")),
            (((-1, -4, 1), (2, -3, 1)), ("VECTOR", "FREE")),
        ):
            spline = data.splines.new("BEZIER")
            spline.bezier_points.add(len(coords) - 1)
            for point, co, kind in zip(spline.bezier_points, coords, types):
                point.co = co
                point.handle_left = point.co - Vector((0.7, 0.4, 0))
                point.handle_right = point.co + Vector((0.7, 0.4, 0))
                point.handle_left_type = point.handle_right_type = kind
        obj = bpy.data.objects.new("Whole Move checks", data)
        bpy.context.collection.objects.link(obj)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        parent = bpy.data.objects.new("Whole Move parent", None)
        bpy.context.collection.objects.link(parent)
        parent.matrix_world = (Matrix.Translation((2, -1, 3)) @ Matrix.Rotation(0.4, 4, "Z")
                               @ Matrix.Diagonal((1.4, 0.8, 1.2, 1)))
        obj.parent = parent
        obj.rotation_euler = (0.2, -0.3, 0.4)
        obj.scale = (1.8, 0.7, 1.1)
        child = bpy.data.objects.new("Whole Move child", None)
        bpy.context.collection.objects.link(child)
        child.parent = obj
        child.location = (1, 2, 3)
        bpy.context.view_layer.update()
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            bpy.ops.spline_maker.enter_selection_level(target="WHOLE")
            bpy.ops.spline_maker.switch_tangent_tool(target="MOVE")
            # Whole selection deliberately includes edit-hidden source points.
            obj.data.splines[1].bezier_points[0].hide = True
            assert module.region_selection.whole_selected(obj.data)
            assert len(drag.selected_anchors(bpy.context)) == 5
            assert bpy.ops.spline_maker.move_drag.poll()
            world = obj.matrix_world.copy()
            parent_world = parent.matrix_world.copy()
            child_world = child.matrix_world.copy()
            view_rotation = Euler((0.5, -0.6, 0.2)).to_quaternion()
            view_matrix = Matrix.Translation((0, 0, -15)) @ view_rotation.to_matrix().to_4x4().inverted()
            fake = SimpleNamespace(
                mode="EDIT_CURVE", edit_object=obj, objects_in_mode=[obj], workspace=bpy.context.workspace,
                window=bpy.context.window,
                area=SimpleNamespace(type="VIEW_3D", tag_redraw=lambda: None,
                                     header_text_set=lambda _: None, as_pointer=lambda: 71),
                region=SimpleNamespace(width=1000, height=700, as_pointer=lambda: 72),
                region_data=SimpleNamespace(view_rotation=view_rotation, view_matrix=view_matrix,
                    perspective_matrix=Matrix.Diagonal((0.08, 0.08, -0.01, 1)) @ view_matrix,
                    is_perspective=False, view_perspective="ORTHO"),
                window_manager=SimpleNamespace(spline_maker_selection_level="WHOLE", modal_handler_add=lambda _: None),
            )

            def points():
                return [p for s in obj.data.splines for p in s.bezier_points]

            def geometry():
                return [drag.snapshot(p) for p in points()]

            def selection():
                return [(p.hide, p.select_control_point, p.select_left_handle, p.select_right_handle) for p in points()]

            def assert_restored(before):
                for actual, expected in zip(geometry(), before):
                    assert all((a - b).length < 2e-5 for a, b in zip(actual[:3], expected[:3]))
                    assert actual[3:] == expected[3:]

            def event(kind, pixel, value="PRESS", ctrl=False):
                return SimpleNamespace(type=kind, value=value, ctrl=ctrl,
                    mouse_region_x=pixel[0], mouse_region_y=pixel[1])

            def begin(axis):
                op = SimpleNamespace(axis=axis, report=lambda *_: None)
                op.update = lambda ctx, evt: cls.update(op, ctx, evt)
                op.finish = lambda ctx, **kwargs: cls.finish(op, ctx, **kwargs)
                start = location_3d_to_region_2d(fake.region, fake.region_data,
                                                obj.matrix_world @ module.feasibility.move_origin(fake))
                assert cls.invoke(op, fake, event("LEFTMOUSE", start)) == {"RUNNING_MODAL"}
                assert len(op.points) == 5 and len({(si, pi) for si, pi, _ in op.points}) == 5
                return op, start

            initial_selection = selection()
            for axis in ("X", "Y", "Z", "XY", "XZ", "YZ", "VIEW"):
                before = geometry()
                op, start = begin(axis)
                end = start + Vector((44, 31))
                assert cls.modal(op, fake, event("MOUSEMOVE", end)) == {"RUNNING_MODAL"}
                delta = world.to_3x3() @ (points()[0].co - before[0][0])
                assert delta.length > 0.1
                if axis != "VIEW":
                    assert all(abs(delta[i]) < 2e-5 for i, letter in enumerate("XYZ") if letter not in axis)
                else:
                    assert abs(delta.dot(view_rotation @ Vector((0, 0, 1)))) < 2e-5
                for p, state in zip(points(), before):
                    for actual, original in zip((p.co, p.handle_left, p.handle_right), state[:3]):
                        assert (world.to_3x3() @ (actual - original) - delta).length < 2e-5
                    assert (p.handle_left_type, p.handle_right_type) == state[3:]
                preview = geometry()
                cls.modal(op, fake, event("MOUSEMOVE", end))
                assert_restored(preview)  # Repeated updates never compound.
                assert selection() == initial_selection
                assert cls.modal(op, fake, event("ESC", end)) == {"CANCELLED"}
                assert_restored(before)
                assert drag._active is None and obj.matrix_world == world
                assert parent.matrix_world == parent_world and child.matrix_world == child_world

            before = geometry()
            for key, ctrl in (("RIGHTMOUSE", False), ("Z", True), ("WINDOW_DEACTIVATE", False)):
                op, start = begin("VIEW")
                end = start + Vector((20, 15))
                cls.modal(op, fake, event("MOUSEMOVE", end))
                assert cls.modal(op, fake, event(key, end, ctrl=ctrl)) == {"CANCELLED"}
                assert_restored(before)
            op, start = begin("VIEW")
            assert cls.modal(op, fake, event("LEFTMOUSE", start, "RELEASE")) == {"CANCELLED"}
            assert_restored(before)
            # Switching tools and disabling must roll back the active preview.
            for stop in (lambda: bpy.ops.spline_maker.switch_tangent_tool(target="SELECT"), drag.unregister):
                bpy.ops.spline_maker.switch_tangent_tool(target="MOVE")
                op, start = begin("VIEW")
                cls.modal(op, fake, event("MOUSEMOVE", start + Vector((20, 15))))
                stop()
                assert_restored(before)
                assert drag._active is None

            bpy.ops.spline_maker.switch_tangent_tool(target="MOVE")
            module.region_selection.select_whole(obj.data, False)
            assert not bpy.ops.spline_maker.move_drag.poll()
            assert module.feasibility.move_origin(bpy.context) is None
            module.region_selection.select_whole(obj.data, True)
            bpy.ops.ed.undo_push(message="Before Whole curve Move")
            op, start = begin("VIEW")
            end = start + Vector((35, 23))
            assert cls.modal(op, fake, event("LEFTMOUSE", end, "RELEASE")) == {"FINISHED"}
            moved = geometry()
            bpy.ops.ed.undo_push(message="After Whole curve Move")
            assert bpy.ops.ed.undo() == {"FINISHED"}
            obj = bpy.context.edit_object  # Native undo invalidates prior data references.
            assert_restored(before)
            assert selection() == initial_selection and obj.matrix_world == world
            assert bpy.ops.ed.redo() == {"FINISHED"}
            obj = bpy.context.edit_object
            assert_restored(moved)
            assert selection() == initial_selection and obj.matrix_world == world
            assert module.region_selection.whole_selected(obj.data)
            print("SM-014 Whole Move axes/planes, hidden points, parent transforms, rollback and native undo/redo passed")
        finally:
            drag.unregister()
            bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
            bpy.ops.object.mode_set(mode="OBJECT")
