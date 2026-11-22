"""Verify live sweep dimensions and source-curve editing in Blender."""

from collections import Counter
from math import cos, hypot, isfinite, pi, radians, sin

import bpy
from mathutils import Vector

from lifecycle_checks import activate, geometry, viewport


def line(name):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(1)
    for point, x, radius in zip(spline.bezier_points, (0, 3), (0.2, 2.0)):
        point.co = (x, 0, 0)
        point.handle_left_type = point.handle_right_type = "VECTOR"
        point.radius = radius
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    activate(obj)
    return obj


def evaluated_mesh(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return [p.co.copy() for p in mesh.vertices], [tuple(p.vertices) for p in mesh.polygons]
    finally:
        evaluated.to_mesh_clear()


def assert_bounds(coords, low, high):
    for axis in range(3):
        actual = (min(p[axis] for p in coords), max(p[axis] for p in coords))
        assert all(abs(a - b) < 1e-5 for a, b in zip(actual, (low[axis], high[axis]))), (axis, actual)


def assert_closed_surface(faces):
    counts = Counter(tuple(sorted((first, second))) for face in faces
                     for first, second in zip(face, (*face[1:], face[0])))
    assert counts and set(counts.values()) == {2}


def check_bounds(profile):
    obj = line("Profile bounds")
    name = obj.name
    original = geometry(obj)
    assert profile.profile_modifier(obj) is None and not evaluated_mesh(obj)[1]
    assert bpy.ops.ed.undo_push(message="Before Make Profile") == {"FINISHED"}
    assert bpy.ops.spline_maker.toggle_profile("EXEC_DEFAULT", True) == {"FINISHED"}
    modifier = profile.profile_modifier(obj)
    assert modifier is not None and modifier.show_viewport and modifier.show_render
    ins = lambda field: profile.profile_input(modifier, field)
    assert ins("Shape").value == "Rectangle"
    assert ins("Height").value == ins("Width").value == 1.0 and ins("Roll").value == 0.0
    assert ins("Height").bl_rna.properties["value"].unit == "LENGTH"
    assert ins("Roll").bl_rna.properties["value"].unit == "ROTATION"
    coords, faces = evaluated_mesh(obj)
    assert len(coords) == 8 and len(faces) == 6
    assert_bounds(coords, (0, -0.5, -0.5), (3, 0.5, 0.5))
    assert_closed_surface(faces)

    assert bpy.ops.ed.undo() == {"FINISHED"}
    assert not profile.profile_modifier(bpy.data.objects[name])
    assert bpy.ops.ed.redo() == {"FINISHED"}
    obj = bpy.data.objects[name]
    modifier = profile.profile_modifier(obj)
    assert modifier.show_viewport
    ins("Height").value = 2.25
    obj.update_tag()
    assert_bounds(evaluated_mesh(obj)[0], (0, -0.5, -1.125), (3, 0.5, 1.125))
    ins("Roll").value = pi / 2
    obj.update_tag()
    assert_bounds(evaluated_mesh(obj)[0], (0, -1.125, -0.5), (3, 1.125, 0.5))

    ins("Shape").value = "Circle"
    ins("Radius").value = 0.75
    obj.update_tag()
    coords, faces = evaluated_mesh(obj)
    assert len(coords) == 64 and len(faces) == 34
    assert all(abs(hypot(p.y, p.z) - 0.75) < 1e-5 for p in coords)
    assert_closed_surface(faces)
    assert geometry(obj) == original and obj.type == "CURVE"
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    assert not modifier.show_viewport and not modifier.show_render and not evaluated_mesh(obj)[1]
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    assert len(obj.modifiers) == 1 and ins("Shape").value == "Circle" and ins("Height").value == 2.25
    assert len(evaluated_mesh(obj)[1]) == 34

    assert bpy.ops.spline_maker.enter_edit(target="SEGMENT") == {"FINISHED"}
    point = obj.data.splines[0].bezier_points[1]
    point.co.x = 5
    assert len(evaluated_mesh(obj)[1]) == 34
    assert_bounds(evaluated_mesh(obj)[0], (0, -0.75, -0.75), (5, 0.75, 0.75))
    assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    assert obj.data.splines[0].bezier_points[1].co == Vector((5, 0, 0))


def check_units_and_attachment(profile):
    units = bpy.context.scene.unit_settings
    old_system, old_scale = units.system, units.scale_length
    units.system, units.scale_length = "IMPERIAL", 0.5
    try:
        target = line("Imperial profile")
        assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
        modifier = profile.profile_modifier(target)
        for field, feet in (("Height", 1), ("Width", 1), ("Radius", 0.5)):
            assert abs(profile.profile_input(modifier, field).value * units.scale_length - 0.3048 * feet) < 1e-6
        profile.profile_input(modifier, "Height").value = 8 * 0.3048 / units.scale_length
        target.update_tag()
        assert_bounds(evaluated_mesh(target)[0], (0, -0.3048, -2.4384), (3, 0.3048, 2.4384))

        source = line("Profile attachment source")
        source.location.y = 4
        assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
        assert profile.profile_modifier(source).node_group == modifier.node_group
        assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
        activate(target, extend=True)
        bpy.context.view_layer.update()
        assert bpy.ops.spline_maker.attach_curves() == {"FINISHED"}
        assert len(target.data.splines) == 2
        coords, faces = evaluated_mesh(target)
        assert len(faces) == 12
        assert_bounds(coords, (0, -0.3048, -2.4384), (3, 4.3048, 2.4384))

        spline = target.data.splines[0]
        spline.bezier_points.add(1)
        tip = spline.bezier_points[-1]
        tip.co = (2, 2, 0)
        tip.handle_left_type = tip.handle_right_type = "AUTO"
        spline.use_cyclic_u = True
        coords, faces = evaluated_mesh(target)
        assert len(faces) > 12
        assert_closed_surface(faces)
        assert all(abs(p.z) <= 2.43841 for p in coords)
    finally:
        units.system, units.scale_length = old_system, old_scale


def check_resolution():
    obj = line("Profile resolution")
    a, b = obj.data.splines[0].bezier_points
    a.handle_right_type = b.handle_left_type = "FREE"
    a.handle_right = (0, 2, 0)
    b.handle_left = (3, 2, 0)
    original = geometry(obj)
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    obj.data.resolution_u = 4
    coarse, coarse_faces = evaluated_mesh(obj)
    obj.data.resolution_u = 32
    fine, fine_faces = evaluated_mesh(obj)
    assert len(fine) > len(coarse) * 4 and len(fine_faces) > len(coarse_faces) * 4
    assert_closed_surface(fine_faces)
    assert geometry(obj) == original


def polygon_path(name, coords, *, closed=False, free=False):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(len(coords) - 1)
    coordinates = [Vector(co) for co in coords]
    spline.use_cyclic_u = closed
    for i, point in enumerate(spline.bezier_points):
        point.co = coordinates[i]
        if free:
            # Collinear handles evaluate many closely spaced rings on both
            # sides of a sharp turn, even though the spans are straight.
            point.handle_left = point.co.lerp(coordinates[max(i - 1, 0)], 0.1)
            point.handle_right = point.co.lerp(coordinates[min(i + 1, len(coords) - 1)], 0.1)
        else:
            point.handle_left_type = point.handle_right_type = "VECTOR"
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    activate(obj)
    return obj


def check_miters():
    for angle, free in ((90, True), (-90, False), (60, False), (105, False), (165, False)):
        turn = radians(angle)
        tip = Vector((4, 0, 0))
        outgoing = Vector((cos(turn), sin(turn), 0))
        coords = [(0, 0, 0), tip, tip + outgoing * 4]
        obj = polygon_path(f"Profile bend {angle}", coords, free=free)
        original = geometry(obj)
        assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
        verts, faces = evaluated_mesh(obj)
        assert len(verts) == 12 and len(faces) == 10, (angle, len(verts), len(faces))
        assert_closed_surface(faces)
        ring = verts[4:8]
        outgoing_normal = Vector((-sin(turn), cos(turn), 0))
        if abs(angle) <= 120:
            for point in ring:
                assert abs(abs(point.y) - 0.5) < 1e-5, (angle, tuple(point))
                assert abs(abs((point - tip).dot(outgoing_normal)) - 0.5) < 1e-5
        else:
            assert all(hypot(p.x - tip.x, p.y - tip.y) <= 1.00001 for p in ring)
        assert all(abs(abs(point.z) - 0.5) < 1e-5 for point in verts)
        assert geometry(obj) == original

    square = ((0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0))
    for winding in (square, tuple(reversed(square))):
        obj = polygon_path("Closed miter", winding, closed=True)
        assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
        corners, faces = evaluated_mesh(obj)
        assert len(corners) == 16 and len(faces) == 16
        assert_closed_surface(faces)
        for i, (x, y, _) in enumerate(winding):
            assert all(abs(abs(p.x - x) - 0.5) < 1e-5 and abs(abs(p.y - y) - 0.5) < 1e-5
                       for p in corners[i * 4:i * 4 + 4])

    repeated = polygon_path("Repeated points near miter", ((0, 0, 0), (4, 0, 0), (4, 0, 0), (4, 4, 0)))
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    verts, _ = evaluated_mesh(repeated)
    assert verts and all(isfinite(axis) for vertex in verts for axis in vertex)

    twisted = polygon_path("Tilt along a straight profile", ((0, 0, 0), (4, 0, 0), (8, 0, 0)))
    twisted.data.splines[0].bezier_points[1].tilt = pi / 4
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    verts, faces = evaluated_mesh(twisted)
    assert len(verts) == 12 and len(faces) == 10
    assert all(abs(hypot(p.y, p.z) - 2 ** -0.5) < 1e-5 for p in verts)
    assert any(abs(abs(p.y) - 2 ** -0.5) < 1e-5 for p in verts[4:8])


def check_remembered_dimensions(profile):
    def dimension(obj, name):
        return profile.profile_input(profile.profile_modifier(obj), name).value

    first = line("First profile dimensions")
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    assert bpy.ops.spline_maker.set_profile_dimension(dimension="Height", value=2.75) == {"FINISHED"}
    assert bpy.ops.spline_maker.set_profile_dimension(dimension="Width", value=0.375) == {"FINISHED"}
    assert profile.profile_modifier(first).node_group.use_fake_user
    assert_bounds(evaluated_mesh(first)[0], (0, -0.1875, -1.375), (3, 0.1875, 1.375))
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}

    second = line("Second profile dimensions")
    assert profile.profile_modifier(second) is None
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    assert dimension(second, "Height") == 2.75 and dimension(second, "Width") == 0.375
    assert bpy.ops.spline_maker.set_profile_dimension(dimension="Width", value=0.5) == {"FINISHED"}
    activate(first)
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    assert dimension(first, "Height") == 2.75 and dimension(first, "Width") == 0.375
    assert bpy.ops.spline_maker.set_profile_dimension(dimension="Height", value=3.25) == {"FINISHED"}
    third = line("Third profile dimensions")
    assert bpy.ops.spline_maker.toggle_profile() == {"FINISHED"}
    assert dimension(third, "Height") == 3.25 and dimension(third, "Width") == 0.5


def run(module):
    with viewport():
        check_bounds(module.profile)
        check_units_and_attachment(module.profile)
        check_resolution()
        check_miters()
        check_remembered_dimensions(module.profile)
    print("M5 live rectangle, roll, circle, Imperial dimensions, and source path editing passed")
    print("M5 native curve resolution and independent remembered rectangle dimensions passed")
    print("M5 mitered inside/outside bends, closed seams, and bounded sharp turns passed")
