"""Make Planar projection, selection scope, and native history checks."""

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from insert_vertex_checks import create_curve
from lifecycle_checks import activate, geometry, viewport


def assert_projection(before, after, world, origin, normal, selected):
    for si, (original, actual) in enumerate(zip(before, after)):
        assert original[0] == actual[0]
        for pi, (source, result) in enumerate(zip(original[1], actual[1])):
            for coordinate, output in zip(source[:3], result[:3]):
                expected = world @ Vector(coordinate)
                if (si, pi) in selected:
                    expected -= (expected - origin).dot(normal) * normal
                assert (world @ Vector(output) - expected).length < 1e-5, ((si, pi), output, expected)


def check_drawing_plane(module):
    drawing = module.drawing_plane
    plane = drawing.DrawingPlane(Vector((1, 2, 5)), Euler((0.4, 0.7, 0.2)).to_quaternion())
    session = drawing.DrawingSession(plane)
    session.place(Vector((-2, 1, 0)))
    session.place(Vector((1, 3, 0)), Vector((1, 1, 0)))
    session.place(Vector((4, -2, 0)))
    session.place(Vector((5, 3, 0)))
    obj = module.drawing_probe.commit_curve(bpy.context, session, closed=True)
    parent = bpy.data.objects.new("Drawing Plane parent", None)
    bpy.context.collection.objects.link(parent)
    parent.matrix_world = Matrix.Rotation(0.37, 4, "X") @ Matrix.Diagonal((1.9, 0.7, 1.5, 1))
    obj.parent = parent
    obj.scale = (0.9, 1.25, 2)
    bpy.context.view_layer.update()
    assert module.make_planar.has_drawing_plane(obj.data)
    points = obj.data.splines[0].bezier_points
    points[3].handle_left_type = points[3].handle_right_type = "AUTO"
    points[3].co.z = 2
    points[2].co.z = -1.5
    points[1].co.z = 1
    assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
    assert bpy.ops.spline_maker.enter_selection_level(target="WHOLE") == {"FINISHED"}
    world = obj.matrix_world.copy()
    before = geometry(obj)
    plane_normal = world.to_3x3().col[0].cross(world.to_3x3().col[1]).normalized()
    assert bpy.ops.ed.undo_push(message="Before Make Planar") == {"FINISHED"}
    assert bpy.ops.spline_maker.make_planar("EXEC_DEFAULT", True, plane="DRAWING") == {"FINISHED"}
    after = geometry(obj)
    assert_projection(before, after, world, world.translation, plane_normal, {(0, i) for i in range(4)})
    assert all(abs(value[2]) < 1e-6 for point in after[0][1] for value in point[:3])
    assert after[0][1][0][3:] == ("VECTOR", "VECTOR")
    assert after[0][1][1][3:] == ("ALIGNED", "ALIGNED")
    assert module.region_selection.whole_selected(obj.data) and obj.matrix_world == world
    assert bpy.ops.spline_maker.make_planar(plane="DRAWING") == {"CANCELLED"}
    assert bpy.ops.ed.undo() == {"FINISHED"}
    assert geometry(bpy.context.edit_object) == before
    assert bpy.ops.ed.redo() == {"FINISHED"}
    assert geometry(bpy.context.edit_object) == after
    assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    assert geometry(bpy.context.object) == after


def check_selection_levels(module):
    view = bpy.context.region_data
    original_rotation = view.view_rotation.copy()
    view.view_rotation = Euler((0.5, 0.1, -0.6)).to_quaternion()
    normal = view.view_rotation @ Vector((0, 0, 1))
    try:
        for level in ("VERTEX", "SEGMENT", "REGION", "WHOLE"):
            obj = create_curve(False, 4, ("FREE",) * 4)
            activate(obj)
            bpy.context.view_layer.update()
            assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
            assert bpy.ops.spline_maker.enter_selection_level(target=level) == {"FINISHED"}
            data = obj.data
            if level == "VERTEX":
                for spline in data.splines:
                    module.vertex_selection.clear_selection(spline.bezier_points)
                assert not bpy.ops.spline_maker.make_planar.poll()
                selected = {(0, 0), (0, 2)}
                for si, pi in selected:
                    data.splines[si].bezier_points[pi].select_control_point = True
            elif level == "SEGMENT":
                module.segment_selection.select(data, {(0, 1), (0, 2)})
                selected = {(0, i) for i in range(1, 4)}
            elif level == "REGION":
                module.region_selection.select_regions(data, {0})
                selected = {(0, i) for i in range(4)}
            else:
                selected = {(0, i) for i in range(4)} | {(1, 0), (1, 1)}
            assert len(module.edit_drag.selected_anchors(bpy.context)) == len(selected)
            assert [item[0] for item in module.make_planar.plane_items(None, bpy.context)] == ["VIEW"]
            world = obj.matrix_world.copy()
            before = geometry(obj)
            center = sum((world @ Vector(before[si][1][pi][0]) for si, pi in selected), Vector()) / len(selected)
            assert bpy.ops.spline_maker.make_planar(plane="VIEW") == {"FINISHED"}
            assert_projection(before, geometry(obj), world, center, normal, selected)
            assert data.splines[1].bezier_points[0].hide and obj.matrix_world == world
            assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}

        obj = create_curve(False, 4, ("FREE",) * 4)
        obj.data.dimensions = "2D"
        activate(obj)
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        assert bpy.ops.spline_maker.enter_selection_level(target="WHOLE") == {"FINISHED"}
        before = geometry(obj)
        assert bpy.ops.spline_maker.make_planar(plane="VIEW") == {"CANCELLED"}
        assert geometry(obj) == before and obj.data.dimensions == "2D"
        view.view_rotation = Quaternion()
        assert bpy.ops.spline_maker.make_planar(plane="VIEW") == {"CANCELLED"}
        assert geometry(obj) == before
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
        obj.scale.z = 0
        bpy.context.view_layer.update()
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        assert bpy.ops.spline_maker.enter_selection_level(target="WHOLE") == {"FINISHED"}
        assert bpy.ops.spline_maker.make_planar(plane="VIEW") == {"CANCELLED"}
        assert geometry(obj) == before
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    finally:
        view.view_rotation = original_rotation


def run(module):
    with viewport():
        check_drawing_plane(module)
        check_selection_levels(module)
    print("M6 Make Planar preserved projected anchors and handles at all four levels, with Undo/Redo")
