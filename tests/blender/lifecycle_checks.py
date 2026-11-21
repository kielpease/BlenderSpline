"""Exercise native curve and scene data across a .blend round trip."""

import os
from pathlib import Path

import bpy
from mathutils import Vector


def add_curve(scene, name, *, closed=False):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(2)
    for index, (point, coordinate) in enumerate(zip(
            spline.bezier_points, ((-2, 0, 0), (2, 0, 0), (1, 3, 0)))):
        point.co = coordinate
        tangent = Vector((0.65, 0.28 * (index + 1), 0))
        point.handle_left = point.co - tangent
        point.handle_right = point.co + tangent
        kind = "ALIGNED" if index == 0 else "FREE"
        point.handle_left_type = point.handle_right_type = kind
    spline.use_cyclic_u = closed
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return obj


def geometry(obj):
    return tuple(
        (spline.use_cyclic_u, tuple(
            (tuple(p.co), tuple(p.handle_left), tuple(p.handle_right), p.handle_left_type, p.handle_right_type)
            for p in spline.bezier_points
        )) for spline in obj.data.splines
    )


def viewport():
    window = bpy.context.window
    area = next(area for area in window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    return bpy.context.temp_override(window=window, area=area, region=region)


def activate(obj, *, extend=False):
    if not extend:
        for item in bpy.context.selected_objects:
            item.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def run(module):
    context = bpy.context
    scene = bpy.data.scenes.new("Splines lifecycle")
    other_scene = bpy.data.scenes.new("Splines second scene")
    context.window.scene = scene
    first = add_curve(scene, "Saved closed curve", closed=True)
    second = add_curve(scene, "Saved open curve")
    other = add_curve(other_scene, "Saved second scene curve")
    second.location = (4, 1, 1)
    other.scale = (1.5, 0.7, 2)

    with viewport():
        activate(first)
        activate(second, extend=True)
        assert not bpy.ops.spline_maker.enter_edit.poll()
        assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
        assert len(context.objects_in_mode) == 2
        assert not module.vertex_selection.supported_curve(context)
        assert not bpy.ops.spline_maker.select_shortcut.poll()
        assert bpy.ops.object.mode_set(mode="OBJECT") == {"FINISHED"}
        for obj in (first, second):
            activate(obj)
            assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
            assert context.edit_object == obj
            if obj == first:
                before = geometry(first)
                assert bpy.ops.spline_maker.selection_level(target="WHOLE") == {"FINISHED"}
                assert bpy.ops.spline_maker.set_selection_coordinate(axis="Z", value=1.75) == {"FINISHED"}
                assert geometry(first) != before
            assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
        assert set(module.display.object_curves(context)) == {first}

    context.window.scene = other_scene
    with viewport():
        activate(other)
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        assert bpy.ops.spline_maker.switch_tangent_tool(target="MOVE") == {"FINISHED"}
        assert bpy.ops.object.mode_set(mode="OBJECT") == {"FINISHED"}
        assert bpy.ops.wm.tool_set_by_id(name=module.drawing_probe.SplineMakerDrawTool.bl_idname) == {"FINISHED"}
        context.window_manager.spline_maker_selection_level = "REGION"
        context.window_manager.spline_maker_vertex_rotation = "GROUP"
        context.window_manager.spline_maker_bright_curves = False
        context.window_manager.spline_maker_curve_color = (0.1, 0.2, 0.3)
        assert module.region_selection.regions(first.data)
        assert module.region_selection._cache_key is not None
    saved = {obj.name: (obj.users_scene[0].name, geometry(obj), tuple(obj.location), tuple(obj.scale))
             for obj in (first, second, other)}

    path = Path(os.environ["BLENDER_USER_RESOURCES"]) / "lifecycle.blend"
    assert bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=False) == {"FINISHED"}
    assert module.region_selection._cache_key is None
    assert bpy.ops.wm.open_mainfile(filepath=str(path)) == {"FINISHED"}
    assert context.scene.name == "Splines second scene"
    assert context.object.name == "Saved second scene curve"
    assert not any(module.lifecycle.active_gestures())

    manager = context.window_manager
    assert manager.spline_maker_selection_level == "VERTEX"
    assert manager.spline_maker_vertex_rotation == "TANGENTS"
    assert manager.spline_maker_bright_curves
    assert all(abs(actual - expected) < 1e-6 for actual, expected in
               zip(manager.spline_maker_curve_color, (0.65, 0.8, 0.95)))
    for name, (scene_name, state, location, scale) in saved.items():
        obj = bpy.data.objects[name]
        assert [item.name for item in obj.users_scene] == [scene_name]
        assert geometry(obj) == state, name
        assert tuple(obj.location) == location and tuple(obj.scale) == scale, name

    context.window.scene = bpy.data.scenes["Splines lifecycle"]
    with viewport():
        activate(bpy.data.objects["Saved closed curve"])
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
        assert geometry(context.object) == saved[context.object.name][1]
    print("SM-017 multiple objects/scenes, native Bézier data, and session settings passed save/reopen")
