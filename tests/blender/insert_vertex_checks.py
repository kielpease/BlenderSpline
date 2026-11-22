"""Verify native Bézier shape and history at arbitrary insert parameters."""

from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

from control_checks import Layout
from lifecycle_checks import activate, viewport


def check_coordinates(module):
    edit = module.edit_drag
    context = bpy.context
    obj = context.edit_object
    fake = SimpleNamespace(mode=context.mode, edit_object=obj, area=context.area,
                           objects_in_mode=context.objects_in_mode,
                           window_manager=SimpleNamespace(clipboard=""))
    anchor = edit.selected_anchors(fake)[0]
    before = obj.matrix_world @ anchor.co
    copy = edit.SPLINE_MAKER_OT_copy_selection_coordinate
    paste = edit.SPLINE_MAKER_OT_set_selection_coordinate
    assert copy.execute(SimpleNamespace(axis="Y"), fake) == {"FINISHED"}
    assert abs(float(fake.window_manager.clipboard) - before.y) < 1e-6
    action = SimpleNamespace(axis="Y", value=0.0, paste=True, report=lambda *_: None)
    for invalid in ("1 2", "nan", "1e300"):
        fake.window_manager.clipboard = invalid
        assert paste.execute(action, fake) == {"CANCELLED"}
        assert obj.matrix_world @ anchor.co == before
    fake.window_manager.clipboard = " 12.75 "
    assert paste.execute(action, fake) == {"FINISHED"}
    assert ((obj.matrix_world @ anchor.co) - Vector((before.x, 12.75, before.z))).length < 2e-5
    layout = Layout()
    button = SimpleNamespace(bl_rna=bpy.ops.spline_maker.set_selection_coordinate.get_rna_type(), axis="Y")
    edit.draw_coordinate_context_menu(SimpleNamespace(layout=layout), SimpleNamespace(button_operator=button))
    assert [(name, item.ui_kwargs["text"], item.axis) for name, item in layout.operators] == [
        ("spline_maker.copy_selection_coordinate", "Copy Value", "Y"),
        ("spline_maker.set_selection_coordinate", "Paste Value", "Y"),
    ]
    assert layout.operators[1][1].paste is True


def cubic(points, t):
    s = 1 - t
    return s ** 3 * points[0] + 3 * s * s * t * points[1] + 3 * s * t * t * points[2] + t ** 3 * points[3]


def create_curve(closed, count, kinds):
    data = bpy.data.curves.new("Add Vert fixture", "CURVE")
    data.dimensions = "3D"
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(count - 1)
    spline.use_cyclic_u = closed
    for i, (point, kind) in enumerate(zip(spline.bezier_points, kinds)):
        point.co = ((-2, 0, 0), (2, 0, 0.5), (2.5, 3, -0.5), (-2, 3, 0))[i]
        tangent = Vector(((0.85, 1.4, 0.2), (0.65, -1.05, 0.3), (-0.8, 0.2, 0), (-0.5, -1, -0.3))[i])
        point.handle_left = point.co - tangent
        point.handle_right = point.co + tangent
        point.handle_left_type = point.handle_right_type = kind
        point.radius = 1 + i
        point.tilt = i * 0.3
    other = data.splines.new("BEZIER")
    other.bezier_points.add(1)
    for i, point in enumerate(other.bezier_points):
        point.co = (5 + i, i, 0)
        point.hide = True
    obj = bpy.data.objects.new("Add Vert fixture", data)
    bpy.context.collection.objects.link(obj)
    obj.matrix_world = Matrix.Translation((0.5, 1, 0.2)) @ Matrix.Diagonal((1.3, 0.9, 1.4, 1))
    return obj


def run(module):
    seg = module.segment_selection

    def spans(data):
        return {key: (a.co.copy(), a.handle_right.copy(), b.handle_left.copy(), b.co.copy())
                for key, a, b in seg.segments(data, include_hidden=True)}

    def assert_span(actual, expected):
        assert all((a - b).length < 2e-5 for a, b in zip(actual, expected)), (actual, expected)

    with viewport():
        for closed, count, start, kinds in (
            (False, 4, 1, ("AUTO", "AUTO", "VECTOR", "ALIGNED")),
            (False, 2, 0, ("VECTOR", "VECTOR")),
            (True, 4, 3, ("FREE", "AUTO", "ALIGNED", "ALIGNED")),
            (True, 2, 0, ("FREE", "FREE")),
            (True, 2, 1, ("FREE", "FREE")),
        ):
            obj = create_curve(closed, count, kinds)
            activate(obj)
            assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
            bpy.context.view_layer.update()
            before = spans(obj.data)
            factor = 0.31
            end = (start + 1) % count
            points = obj.data.splines[0].bezier_points
            radius = (1 - factor) * points[start].radius + factor * points[end].radius
            projected = lambda p: (p.x * 90 / (1 + p.z * 0.08), p.y * 90 / (1 + p.z * 0.08))
            target = projected(obj.matrix_world @ cubic(before[(0, start)], factor))
            hit = module.insert_vertex.pick(obj.data, obj.matrix_world, projected, target)
            assert hit is not None and hit[0] == (0, start) and abs(hit[1] - factor) < 1e-4, hit
            assert module.insert_vertex.pick(obj.data, obj.matrix_world, projected, (10000, 10000)) is None
            assert bpy.ops.spline_maker.add_vert(spline_index=1, segment_index=0, factor=factor) == {"CANCELLED"}
            assert spans(obj.data) == before
            assert bpy.ops.ed.undo_push(message="Before Add Vert") == {"FINISHED"}
            assert bpy.ops.spline_maker.add_vert("EXEC_DEFAULT", True, spline_index=0,
                                                 segment_index=start, factor=factor) == {"FINISHED"}
            bpy.context.view_layer.update()
            edited = spans(obj.data)
            assert obj.data.splines[0].use_cyclic_u == closed
            points = obj.data.splines[0].bezier_points
            assert len(points) == count + 1 and abs(points[start + 1].radius - radius) < 1e-6
            assert [i for i, point in enumerate(points) if point.select_control_point] == [start + 1]
            assert all(point.hide for point in obj.data.splines[1].bezier_points)

            for i in range(21):
                sample = i / 20
                assert (cubic(edited[(0, start)], sample) - cubic(before[(0, start)], sample * factor)).length < 2e-5
                assert (cubic(edited[(0, start + 1)], sample)
                        - cubic(before[(0, start)], factor + (1 - factor) * sample)).length < 2e-5
            for (si, index), expected in before.items():
                if (si, index) != (0, start):
                    adjusted = index + int(si == 0 and index > start)
                    assert_span(edited[(si, adjusted)], expected)

            assert bpy.ops.ed.undo() == {"FINISHED"}
            assert bpy.context.mode == "EDIT_CURVE"
            obj = bpy.context.edit_object
            assert len(obj.data.splines[0].bezier_points) == count
            for key, expected in before.items():
                assert_span(spans(obj.data)[key], expected)
            assert bpy.ops.ed.redo() == {"FINISHED"}
            obj = bpy.context.edit_object
            assert len(obj.data.splines[0].bezier_points) == count + 1
            for key, expected in edited.items():
                assert_span(spans(obj.data)[key], expected)
            if closed and count == 2 and start == 1:
                check_coordinates(module)
            assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    print("M6 Add Vert projected picking, native shape preservation, and single-step Undo/Redo passed")
    print("M6 axis copy/paste, invalid clipboard input, and context-menu operator routing passed")
