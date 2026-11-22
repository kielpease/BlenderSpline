"""Native Attach, Detach, and Weld regression checks."""

from time import perf_counter

import bpy
from mathutils import Matrix, Quaternion, Vector

from insert_vertex_checks import create_curve
from lifecycle_checks import activate, geometry, viewport


def world_paths(obj):
    return [(s.use_cyclic_u, [(obj.matrix_world @ p.co, obj.matrix_world @ p.handle_left,
                             obj.matrix_world @ p.handle_right) for p in s.bezier_points])
            for s in obj.data.splines]


def assert_world_paths(actual, expected):
    assert len(actual) == len(expected)
    for (closed, points), (was_closed, original) in zip(actual, expected):
        assert closed == was_closed and len(points) == len(original)
        for point, state in zip(points, original):
            assert all((a - b).length < 3e-5 for a, b in zip(point, state)), (point, state)


def check_attach():
    for shared in (False, True):
        target = create_curve(False, 4, ("ALIGNED", "AUTO", "FREE", "VECTOR"))
        source = create_curve(True, 4, ("AUTO", "AUTO", "VECTOR", "FREE"))
        parent = bpy.data.objects.new("Attach parent", None)
        bpy.context.collection.objects.link(parent)
        parent.matrix_world = (Matrix.Translation((0.2, -1.2, 1)) @ Matrix.Rotation(0.45, 4, "Y")
                               @ Matrix.Diagonal((2.1, 0.8, 1.7, 1)))
        source.parent = parent
        source.matrix_basis = Matrix.Translation((3, 1, 0.5)) @ Matrix.Rotation(0.4, 4, "Z")
        neighbor_name = None
        if shared:
            target.data.dimensions = "2D"
            neighbor = bpy.data.objects.new("Shared attach data", target.data)
            bpy.context.collection.objects.link(neighbor)
            neighbor_name = neighbor.name
        bpy.context.view_layer.update()
        activate(source)
        activate(target, extend=True)
        assert bpy.ops.spline_maker.attach_curves.poll()
        target_name, source_name = target.name, source.name
        target_world = target.matrix_world.copy()
        target_path, source_path = world_paths(target), world_paths(source)
        target_original = geometry(target)
        assert bpy.ops.ed.undo_push(message="Before Attach") == {"FINISHED"}
        assert bpy.ops.spline_maker.attach_curves("EXEC_DEFAULT", True) == {"FINISHED"}
        assert bpy.context.object == target and target.matrix_world == target_world
        assert source_name not in bpy.context.view_layer.objects
        assert_world_paths(world_paths(target), target_path + source_path)
        assert target.data.dimensions == "3D"
        if neighbor_name:
            assert geometry(bpy.data.objects[neighbor_name]) == target_original
            assert bpy.data.objects[neighbor_name].data != target.data
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert bpy.context.mode == "OBJECT"
        assert {obj.name for obj in bpy.context.selected_objects} == {target_name, source_name}
        assert_world_paths(world_paths(bpy.data.objects[target_name]), target_path)
        assert_world_paths(world_paths(bpy.data.objects[source_name]), source_path)
        assert bpy.ops.ed.redo() == {"FINISHED"}
        target = bpy.context.object
        assert target.name == target_name and source_name not in bpy.context.view_layer.objects
        assert_world_paths(world_paths(target), target_path + source_path)
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        assert bpy.ops.spline_maker.enter_selection_level(target="WHOLE") == {"FINISHED"}
        assert len(target.data.splines) == len(target_path) + len(source_path)
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}


def add_open_path(data):
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(2)
    for i, point in enumerate(spline.bezier_points):
        point.co = (5 + i, 1 - i, 0)
        point.handle_left_type = point.handle_right_type = "FREE"
        point.handle_left = point.co + Vector((-0.8, 0.6, 0.2))
        point.handle_right = point.co + Vector((0.3, -0.6, -0.4))
        point.tilt = 0.15 * (i + 1)
        point.radius = 1 + i
    return spline


def check_detach(module):
    for selected in ({0}, {0, 2}):
        obj = create_curve(selected == {0}, 4, ("AUTO", "VECTOR", "ALIGNED", "FREE"))
        add_open_path(obj.data)
        obj.rotation_euler.y = 0.3
        obj.data.bevel_depth = 0.04
        obj.data.use_fake_user = True
        activate(obj)
        bpy.context.view_layer.update()
        original_name = obj.name
        original_matrix = obj.matrix_world.copy()
        prior_objects = {item.name for item in bpy.context.scene.objects}
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        assert not bpy.ops.spline_maker.detach_splines.poll()
        assert bpy.ops.spline_maker.enter_selection_level(target="REGION") == {"FINISHED"}
        assert not bpy.ops.spline_maker.detach_splines.poll()
        module.region_selection.select_regions(obj.data, selected)
        # An edit-hidden path may retain flags from a previous selection level.
        for point in obj.data.splines[1].bezier_points:
            point.select_control_point = point.select_left_handle = point.select_right_handle = True
        if 2 not in selected:
            obj.data.splines[2].bezier_points[0].select_left_handle = True
        assert module.region_selection.selected_regions(obj.data) == selected
        assert bpy.ops.spline_maker.detach_splines.poll()
        original = geometry(obj)
        source_state = tuple(path for i, path in enumerate(original) if i not in selected)
        detached_state = tuple(path for i, path in enumerate(original) if i in selected)
        assert bpy.ops.ed.undo_push(message="Before Detach") == {"FINISHED"}
        assert bpy.ops.spline_maker.detach_splines("EXEC_DEFAULT", True) == {"FINISHED"}
        bpy.context.view_layer.update()
        new_names = {item.name for item in bpy.context.scene.objects} - prior_objects
        assert len(new_names) == 1
        detached_name = new_names.pop()

        def assert_detached():
            source = bpy.context.edit_object
            detached = bpy.data.objects[detached_name]
            assert source.name == original_name
            assert geometry(source) == source_state and geometry(detached) == detached_state
            assert source.matrix_world == original_matrix and detached.matrix_world == original_matrix
            assert source.data != detached.data and source.data.bevel_depth == detached.data.bevel_depth
            assert all(point.hide for point in source.data.splines[0].bezier_points)

        assert_detached()
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert detached_name not in bpy.context.scene.objects
        assert bpy.context.edit_object.name == original_name
        assert geometry(bpy.context.edit_object) == original
        assert module.region_selection.selected_regions(bpy.context.edit_object.data) == selected
        assert bpy.ops.ed.redo() == {"FINISHED"}
        assert_detached()
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
        assert geometry(bpy.data.objects[original_name]) == source_state

    obj = create_curve(False, 4, ("FREE",) * 4)
    linked = bpy.data.objects.new("Linked Detach guard", obj.data)
    bpy.context.collection.objects.link(linked)
    activate(obj)
    assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
    assert bpy.ops.spline_maker.enter_selection_level(target="REGION") == {"FINISHED"}
    module.region_selection.select_regions(obj.data, {0})
    before = geometry(obj)
    assert bpy.ops.spline_maker.detach_splines() == {"CANCELLED"}
    assert geometry(obj) == before and obj.data == linked.data
    assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}

    bpy.data.objects.remove(linked, do_unlink=True)
    for point in obj.data.splines[1].bezier_points:
        point.hide = False
    assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
    assert bpy.ops.spline_maker.enter_selection_level(target="REGION") == {"FINISHED"}
    module.region_selection.select_regions(obj.data, {0, 1})
    assert not bpy.ops.spline_maker.detach_splines.poll()
    assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}


def check_batch_attach():
    open_curve = create_curve(False, 4, ("FREE", "ALIGNED", "VECTOR", "FREE"))
    closed_curve = create_curve(True, 4, ("AUTO", "AUTO", "VECTOR", "FREE"))
    batch = [open_curve, closed_curve]
    for i in range(2, 256):
        source = batch[i % 2].copy()
        source.name = f"Batch curve {i:03}"
        bpy.context.collection.objects.link(source)
        source.location = (i % 16 * 1.2, i // 16, (i % 5) / 4)
        source.rotation_euler = (0.07 * (i % 9), 0.03 * (i % 7), 0.1 * (i % 11))
        source.scale = (1 + (i % 5) / 10, 0.8, 1.1)
        batch.append(source)
    target = batch[137]
    target_name = target.name
    untouched = create_curve(True, 3, ("FREE",) * 3)
    untouched_name = untouched.name
    untouched_state = geometry(untouched)
    activate(target)
    for source in batch:
        source.select_set(True)
    bpy.context.view_layer.update()
    mesh_data = bpy.data.meshes.new("Mixed selection guard")
    mesh = bpy.data.objects.new(mesh_data.name, mesh_data)
    bpy.context.collection.objects.link(mesh)
    mesh.select_set(True)
    assert not bpy.ops.spline_maker.attach_curves.poll()
    bpy.data.objects.remove(mesh, do_unlink=True)
    bpy.data.meshes.remove(mesh_data)
    selected = bpy.context.selected_editable_objects
    original = {obj.name: world_paths(obj) for obj in selected}
    expected = world_paths(target) + [path for obj in selected if obj != target for path in original[obj.name]]
    assert len(original) == 256 and len(expected) == 512

    child = bpy.data.objects.new("Attach child guard", None)
    bpy.context.collection.objects.link(child)
    child.parent = batch[200]
    assert bpy.ops.spline_maker.attach_curves("EXEC_DEFAULT", True) == {"CANCELLED"}
    assert len(bpy.context.selected_objects) == 256 and len(target.data.splines) == 2
    bpy.data.objects.remove(child, do_unlink=True)
    assert bpy.ops.ed.undo_push(message="Before batch Attach") == {"FINISHED"}
    start = perf_counter()
    assert bpy.ops.spline_maker.attach_curves("EXEC_DEFAULT", True) == {"FINISHED"}
    elapsed = perf_counter() - start
    assert bpy.context.object == target
    assert_world_paths(world_paths(target), expected)
    assert geometry(bpy.data.objects[untouched_name]) == untouched_state

    assert bpy.ops.ed.undo() == {"FINISHED"}
    restored = bpy.context.selected_objects
    assert {obj.name for obj in restored} == original.keys()
    for obj in restored:
        assert_world_paths(world_paths(obj), original[obj.name])
    assert bpy.ops.ed.redo() == {"FINISHED"}
    assert bpy.context.object.name == target_name
    assert {obj.name for obj in bpy.context.view_layer.objects}.intersection(original) == {target_name}
    assert_world_paths(world_paths(bpy.context.object), expected)
    assert geometry(bpy.data.objects[untouched_name]) == untouched_state
    print(f"M6 batch Attach preserved 512 paths from 256 objects with one Undo/Redo ({elapsed:.3f} s)")

    view = bpy.context.region_data
    rotation = view.view_rotation.copy()
    view.view_rotation = Quaternion()
    try:
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        assert bpy.ops.spline_maker.enter_selection_level(target="WHOLE") == {"FINISHED"}
        anchors = [point[0] for _, path in expected for point in path]
        depth = sum(point.z for point in anchors) / len(anchors)
        before = geometry(bpy.context.edit_object)
        assert bpy.ops.ed.undo_push(message="Before making attached paths planar") == {"FINISHED"}
        assert bpy.ops.spline_maker.make_planar("EXEC_DEFAULT", True, plane="VIEW") == {"FINISHED"}
        flattened = world_paths(bpy.context.edit_object)
        assert len(flattened) == 512
        assert all(abs(co.z - depth) < 1e-5 for _, path in flattened for point in path for co in point)
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert geometry(bpy.context.edit_object) == before
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    finally:
        view.view_rotation = rotation


def check_weld(module):
    for ends in (None, (0, 0), (0, 2), (3, 0), (3, 2)):
        obj = create_curve(False, 4, ("FREE",) * 4)
        if ends:
            add_open_path(obj.data)
        activate(obj)
        bpy.context.view_layer.update()
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        primary = obj.data.splines[0]
        secondary = obj.data.splines[2] if ends else primary
        a, b = ends or (0, 3)
        point_a, point_b = primary.bezier_points[a], secondary.bezier_points[b]
        for spline in obj.data.splines:
            module.vertex_selection.clear_selection(spline.bezier_points)
        point_a.select_control_point = True
        point_b.select_control_point = True
        before = geometry(obj)
        center = (point_a.co + point_b.co) / 2
        if a == 0:
            incoming = (point_b.handle_right if b == 0 else point_b.handle_left) - point_b.co
            outgoing = point_a.handle_right - point_a.co
            seam = 2 if ends else 0
        else:
            incoming = point_a.handle_left - point_a.co
            outgoing = (point_b.handle_left if b != 0 else point_b.handle_right) - point_b.co
            seam = 3
        untouched = geometry(obj)[1]
        assert bpy.ops.ed.undo_push(message="Before Weld") == {"FINISHED"}
        assert bpy.ops.spline_maker.weld_verts("EXEC_DEFAULT", True) == {"FINISHED"}
        bpy.context.view_layer.update()
        welded = obj.data.splines[-1]
        assert len(obj.data.splines) == 2 and geometry(obj)[0] == untouched
        assert welded.use_cyclic_u == (ends is None)
        assert len(welded.bezier_points) == (6 if ends else 3)
        active = [i for i, point in enumerate(welded.bezier_points) if point.select_control_point]
        assert active == [seam]
        point = welded.bezier_points[seam]
        assert (point.co - center).length < 1e-6
        assert (point.handle_left - center - incoming).length < 1e-6
        assert (point.handle_right - center - outgoing).length < 1e-6
        assert point.handle_left_type == point.handle_right_type == "FREE"
        after = geometry(obj)
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert bpy.context.mode == "EDIT_CURVE" and geometry(bpy.context.edit_object) == before
        assert bpy.ops.ed.redo() == {"FINISHED"}
        assert geometry(bpy.context.edit_object) == after
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
        assert geometry(bpy.context.object) == after

    obj = create_curve(False, 2, ("FREE", "FREE"))
    activate(obj)
    assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
    for point in obj.data.splines[0].bezier_points:
        point.select_control_point = True
    before = geometry(obj)
    assert bpy.ops.spline_maker.weld_verts() == {"CANCELLED"}
    assert geometry(obj) == before
    assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}

    obj = create_curve(True, 4, ("FREE",) * 4)
    activate(obj)
    assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
    original = world_paths(obj)[0][1]
    points = obj.data.splines[0].bezier_points
    module.vertex_selection.clear_selection(points)
    points[2].select_control_point = True
    assert bpy.ops.spline_maker.break_verts() == {"FINISHED"}
    assert module.topology_edit.vertex_keys(obj.data) == {(1, 0), (1, 4)}
    assert bpy.ops.spline_maker.weld_verts() == {"FINISHED"}
    assert_world_paths(world_paths(obj)[-1:], [(True, original[2:] + original[:2])])
    assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}


def run(module):
    with viewport():
        check_attach()
        check_batch_attach()
        check_detach(module)
        check_weld(module)
    print("M6 Attach, Detach, and Weld native geometry, transformed objects, open paths, loops, and Undo/Redo passed")
