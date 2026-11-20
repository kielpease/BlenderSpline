"""SM-015 geometry pivots, world transforms, modal rollback and native undo."""

from math import cos, sin
from types import SimpleNamespace

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Euler, Matrix, Vector


def run(module):
    drag = module.tangent_drag
    cls = drag.SPLINE_MAKER_OT_tangent_drag
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.object.select_all(action="DESELECT")
        data = bpy.data.curves.new("Geometry transforms", "CURVE")
        data.dimensions = "3D"
        for coords in (((-3, -1, 0), (0, 2, 0), (3, 0, 1), (5, -1, 0)),
                       ((0, -6, 0), (3, -6, 0), (1, -3, 0))):
            spline = data.splines.new("BEZIER")
            spline.bezier_points.add(len(coords) - 1)
            for p, co in zip(spline.bezier_points, coords):
                p.handle_left_type = p.handle_right_type = "FREE"
                p.co = co
                p.handle_left = p.co - Vector((0.8, 0.4, 0.2))
                p.handle_right = p.co + Vector((0.8, 0.4, 0.2))
        obj = bpy.data.objects.new("Geometry transforms", data)
        bpy.context.collection.objects.link(obj)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        parent = bpy.data.objects.new("Transform parent", None)
        bpy.context.collection.objects.link(parent)
        parent.matrix_world = (Matrix.Translation((2, -1, 3)) @ Matrix.Rotation(0.4, 4, "Z")
                               @ Matrix.Diagonal((1.4, 0.8, 1.2, 1)))
        obj.parent = parent
        obj.rotation_euler = (0.2, -0.3, 0.4)
        obj.scale = (1.8, 0.7, 1.1)
        bpy.context.view_layer.update()
        world = obj.matrix_world.copy()
        linear = world.to_3x3()
        view_rotation = Euler((0.5, -0.6, 0.2)).to_quaternion()
        view_matrix = Matrix.Translation((0, 0, -15)) @ view_rotation.to_matrix().to_4x4().inverted()
        bpy.ops.object.mode_set(mode="EDIT")
        fake = SimpleNamespace(
            mode="EDIT_CURVE", edit_object=obj, objects_in_mode=[obj], workspace=bpy.context.workspace,
            window=bpy.context.window,
            area=SimpleNamespace(type="VIEW_3D", tag_redraw=lambda: None,
                                 header_text_set=lambda _: None, as_pointer=lambda: 81),
            region=SimpleNamespace(width=1000, height=700, as_pointer=lambda: 82),
            region_data=SimpleNamespace(view_rotation=view_rotation, view_matrix=view_matrix,
                perspective_matrix=Matrix.Diagonal((0.08, 0.08, -0.01, 1)) @ view_matrix,
                is_perspective=False, view_perspective="ORTHO"),
            window_manager=SimpleNamespace(spline_maker_selection_level="SEGMENT", modal_handler_add=lambda _: None),
        )

        def points():
            return {(si, pi): p for si, s in enumerate(obj.data.splines) for pi, p in enumerate(s.bezier_points)}

        def geometry():
            return {key: module.edit_drag.snapshot(p) for key, p in points().items()}

        def flags():
            return [(p.hide, p.select_control_point, p.select_left_handle, p.select_right_handle) for p in points().values()]

        def assert_geometry(expected):
            for key, actual in geometry().items():
                assert all((a - b).length < 5e-5 for a, b in zip(actual[:3], expected[key][:3])), key
                assert actual[3:] == expected[key][3:]

        def assert_transformed(before, selected, pivot, matrix):
            for key, p in points().items():
                state = before[key]
                for actual, original in zip((p.co, p.handle_left, p.handle_right), state[:3]):
                    expected = world @ pivot + matrix @ (world @ original - world @ pivot) if key in selected else world @ original
                    assert (world @ actual - expected).length < 8e-5, (key, tuple(world @ actual), tuple(expected))
            assert obj.matrix_world == world

        def pixel(co):
            return location_3d_to_region_2d(fake.region, fake.region_data, co)

        def event(kind, point, value="PRESS", ctrl=False):
            return SimpleNamespace(type=kind, value=value, ctrl=ctrl, mouse_region_x=point[0], mouse_region_y=point[1])

        def begin(mode, axis):
            bpy.ops.spline_maker.switch_tangent_tool(target=mode)
            op = SimpleNamespace(mode=mode, axis=axis, report=lambda *_: None)
            op.update = lambda ctx, evt: cls.update(op, ctx, evt)
            op.finish = lambda ctx, **kwargs: cls.finish(op, ctx, **kwargs)
            pivot = world @ module.feasibility.move_origin(fake)
            normal = (view_rotation @ Vector((0, 0, 1)) if axis in {"VIEW", "UNIFORM"}
                      else Vector((0, 0, 1)) if axis == "XY"
                      else Vector(tuple(float(letter == axis) for letter in "XYZ")))
            u = normal.orthogonal().normalized()
            start = pixel(pivot + 2 * u) if mode == "ROTATE" else pixel(pivot)
            if axis == "XY":
                start = pixel(pivot + Vector((1, 1, 0)))
            assert cls.invoke(op, fake, event("LEFTMOUSE", start)) == {"RUNNING_MODAL"}, (mode, axis)
            if mode == "ROTATE":
                angle = 0.4
                end = pixel(pivot + 2 * (cos(angle) * u + sin(angle) * normal.cross(u)))
                matrix = Matrix.Rotation(angle, 3, normal)
            elif axis in {"X", "Y", "Z", "XY"}:
                end = start + 40 * op.screen_axis
                matrix = Matrix.Diagonal((1.5, 1.5, 1)) if axis == "XY" else Matrix.Scale(1.5, 3, normal)
            else:
                end = start + Vector((48, 16))
                matrix = Matrix.Scale(1.4, 3)
            return op, start, end, matrix

        try:
            for level, selected in (("SEGMENT", {(0, 0), (0, 1), (0, 2)}),
                                    ("REGION", {(1, 0), (1, 1), (1, 2)}),
                                    ("WHOLE", set(points()))):
                bpy.ops.spline_maker.enter_selection_level(target=level)
                fake.window_manager.spline_maker_selection_level = level
                if level == "SEGMENT":
                    module.segment_selection.select(obj.data, {(0, 0), (0, 1)})
                elif level == "REGION":
                    module.region_selection.select_regions(obj.data, {1})
                else:
                    obj.data.splines[0].bezier_points[3].hide = True
                before, selection = geometry(), flags()
                snapshot = drag.capture(bpy.context)
                assert {(s[0], s[1]) for s in snapshot} == selected
                assert len(snapshot) == len(selected)  # Shared segment endpoint once.
                pivot = sum((before[key][0] for key in selected), Vector()) / len(selected)
                assert (module.feasibility.move_origin(fake) - pivot).length < 1e-6
                matrices = [(Matrix.Rotation(0.6, 3, axis), True) for axis in "XYZ"]
                matrices += [(Matrix.Scale(1.6, 3, Vector((1, 0, 0))), False), (Matrix.Scale(0.6, 3), False),
                             (Matrix.Diagonal((1.6, 1.6, 1)), False)]
                for matrix, rotating in matrices:
                    for _ in range(2):
                        drag.apply(obj.data, snapshot, linear.inverted() @ matrix @ linear, rotating=rotating, pivot=pivot)
                        assert_transformed(before, selected, pivot, matrix)
                        assert flags() == selection
                    drag.restore(obj.data, snapshot)
                    assert_geometry(before)

                for mode, axes in (("ROTATE", ("X", "Y", "Z", "VIEW")),
                                   ("SCALE", ("X", "Y", "Z", "XY", "UNIFORM"))):
                    for axis in axes:
                        op, start, end, matrix = begin(mode, axis)
                        assert_geometry(before)  # No jump on press.
                        cls.modal(op, fake, event("MOUSEMOVE", end))
                        assert_transformed(before, selected, pivot, matrix)
                        cls.modal(op, fake, event("MOUSEMOVE", end))
                        assert_transformed(before, selected, pivot, matrix)
                        group = SimpleNamespace(controls=[(SimpleNamespace(hide=False), mode, Matrix.Identity(4), False)])
                        module.transform_gizmos.VIEW3D_GGT_spline_maker_transform.draw_prepare(group, fake)
                        assert group.controls[0][0].hide  # Preview owns rendering.
                        assert cls.modal(op, fake, event("ESC", end)) == {"CANCELLED"}
                        assert_geometry(before)
                        assert flags() == selection and drag._active is None
                    axis = "VIEW" if mode == "ROTATE" else "UNIFORM"
                    for key, ctrl in (("RIGHTMOUSE", False), ("Z", True), ("WINDOW_DEACTIVATE", False)):
                        op, start, end, matrix = begin(mode, axis)
                        cls.modal(op, fake, event("MOUSEMOVE", end))
                        assert cls.modal(op, fake, event(key, end, ctrl=ctrl)) == {"CANCELLED"}
                        assert_geometry(before)
                    op, start, end, matrix = begin(mode, axis)
                    cls.modal(op, fake, event("MOUSEMOVE", end))
                    cls.modal(op, fake, event("MOUSEMOVE", start))
                    assert not op.changed
                    assert_geometry(before)
                    assert cls.modal(op, fake, event("LEFTMOUSE", start, "RELEASE")) == {"CANCELLED"}
                    for stop in (lambda: bpy.ops.spline_maker.switch_tangent_tool(target="SELECT"), drag.unregister):
                        op, start, end, matrix = begin(mode, axis)
                        cls.modal(op, fake, event("MOUSEMOVE", end))
                        stop()
                        assert_geometry(before)
                        assert drag._active is None
                    # Complete a modal drag, then verify the native undo data.
                    bpy.ops.ed.undo_push(message=f"Before {level} {mode} drag")
                    op, start, end, matrix = begin(mode, axis)
                    assert cls.modal(op, fake, event("LEFTMOUSE", end, "RELEASE")) == {"FINISHED"}
                    assert_transformed(before, selected, pivot, matrix)
                    moved = geometry()
                    bpy.ops.ed.undo_push(message=f"After {level} {mode} drag")
                    assert bpy.ops.ed.undo() == {"FINISHED"}
                    obj = bpy.context.edit_object
                    fake.edit_object, fake.objects_in_mode = obj, [obj]
                    assert_geometry(before)
                    assert bpy.ops.ed.redo() == {"FINISHED"}
                    obj = bpy.context.edit_object
                    fake.edit_object, fake.objects_in_mode = obj, [obj]
                    assert_geometry(moved)
                    drag.restore(obj.data, snapshot)
                    # Discrete buttons use the same center and native Undo data.
                    bpy.ops.spline_maker.switch_tangent_tool(target=mode)
                    bpy.ops.ed.undo_push(message=f"Before {level} {mode}")
                    assert bpy.ops.spline_maker.tangent_step() == {"FINISHED"}
                    moved = geometry()
                    assert moved != before
                    bpy.ops.ed.undo_push(message=f"After {level} {mode}")
                    assert bpy.ops.ed.undo() == {"FINISHED"}
                    obj = bpy.context.edit_object
                    fake.edit_object, fake.objects_in_mode = obj, [obj]
                    assert_geometry(before)
                    assert flags() == selection
                    assert bpy.ops.ed.redo() == {"FINISHED"}
                    obj = bpy.context.edit_object
                    fake.edit_object, fake.objects_in_mode = obj, [obj]
                    assert_geometry(moved)
                    assert flags() == selection
                    drag.restore(obj.data, snapshot)
                    assert_geometry(before)
                obj.data.splines[0].bezier_points[3].hide = False

            # Commit the XY drag and verify both axes scale while world Z is
            # unchanged, including through native Curve Edit Undo/Redo.
            before = geometry()
            selection = flags()
            bpy.ops.ed.undo_push(message="Before XY scale")
            op, start, end, matrix = begin("SCALE", "XY")
            assert cls.modal(op, fake, event("LEFTMOUSE", end, "RELEASE")) == {"FINISHED"}
            assert_transformed(before, selected, pivot, matrix)
            assert all(abs((world @ p.co).z - (world @ before[key][0]).z) < 5e-5 for key, p in points().items())
            moved = geometry()
            bpy.ops.ed.undo_push(message="After XY scale")
            assert bpy.ops.ed.undo() == {"FINISHED"}
            obj = bpy.context.edit_object
            fake.edit_object, fake.objects_in_mode = obj, [obj]
            assert_geometry(before)
            assert flags() == selection
            assert bpy.ops.ed.redo() == {"FINISHED"}
            obj = bpy.context.edit_object
            fake.edit_object, fake.objects_in_mode = obj, [obj]
            assert_geometry(moved)
            drag.restore(obj.data, snapshot)

            # Empty Whole selection disables gizmos/operators, and invalid
            # orthographic axes cancel without starting a modal preview.
            module.region_selection.select_whole(obj.data, False)
            assert not bpy.ops.spline_maker.tangent_drag.poll()
            assert not bpy.ops.spline_maker.tangent_step.poll()
            module.region_selection.select_whole(obj.data, True)
            saved_view = fake.region_data
            fake.region_data = SimpleNamespace(view_rotation=Euler((0, 0, 0)).to_quaternion(),
                view_matrix=Matrix.Translation((0, 0, -15)),
                perspective_matrix=Matrix.Diagonal((0.08, 0.08, -0.01, 1)),
                is_perspective=False, view_perspective="ORTHO")
            for mode, axis in (("ROTATE", "X"), ("SCALE", "Z")):
                op = SimpleNamespace(mode=mode, axis=axis, report=lambda *_: None)
                op.update = lambda ctx, evt: cls.update(op, ctx, evt)
                center = pixel(world @ module.feasibility.move_origin(fake))
                assert cls.invoke(op, fake, event("LEFTMOUSE", center + Vector((60, 0)))) == {"CANCELLED"}
                assert drag._active is None
            fake.region_data = saved_view
            fake.region_data = SimpleNamespace(view_rotation=Euler((0, 1.5707963267948966, 0)).to_quaternion(),
                view_matrix=Matrix.Translation((0, 0, -15)) @ Matrix.Rotation(-1.5707963267948966, 4, "Y"),
                perspective_matrix=Matrix.Diagonal((0.08, 0.08, -0.01, 1)) @ Matrix.Rotation(-1.5707963267948966, 4, "Y"),
                is_perspective=False, view_perspective="ORTHO")
            op = SimpleNamespace(mode="SCALE", axis="XY", report=lambda *_: None)
            op.update = lambda ctx, evt: cls.update(op, ctx, evt)
            assert cls.invoke(op, fake, event("LEFTMOUSE", (600, 400))) == {"CANCELLED"}
            assert drag._active is None
            fake.region_data = saved_view

            # Whole geometry preserves all vertex types, including native Auto/Vector.
            bpy.ops.object.mode_set(mode="OBJECT")
            for p, kind in zip(obj.data.splines[0].bezier_points, ("VECTOR", "AUTO", "ALIGNED", "FREE")):
                p.handle_left_type = p.handle_right_type = kind
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.spline_maker.enter_selection_level(target="WHOLE")
            bpy.ops.spline_maker.switch_tangent_tool(target="SCALE")
            original_types = [(p.handle_left_type, p.handle_right_type) for p in points().values()]
            bpy.ops.ed.undo_push(message="Typed curve before scale")
            original_anchors = [p.co.copy() for p in points().values()]
            center = module.feasibility.move_origin(bpy.context).copy()
            bpy.ops.spline_maker.tangent_step()
            bpy.ops.ed.undo_push(message="Typed curve scaled")
            assert [(p.handle_left_type, p.handle_right_type) for p in points().values()] == original_types
            assert all((p.co - center - 1.25 * (co - center)).length < 5e-5
                       for p, co in zip(points().values(), original_anchors))
            assert bpy.ops.ed.undo() == {"FINISHED"}
            obj = bpy.context.edit_object
            assert all((p.co - co).length < 5e-5 for p, co in zip(points().values(), original_anchors))
            assert [(p.handle_left_type, p.handle_right_type) for p in points().values()] == original_types
            print("SM-015 centered Segment/Spline/Whole rotate/scale, parent transforms, modal rollback and native undo/redo passed")
        finally:
            drag.unregister()
            module.transform_gizmos.unregister()
            bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
            bpy.ops.object.mode_set(mode="OBJECT")
