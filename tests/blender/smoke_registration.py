"""Install a local package and check the enable, disable, re-enable cycle."""

import importlib
from math import radians
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import bpy
from bpy_extras import view3d_utils
from mathutils import Matrix, Quaternion, Vector


def main(archive):
    prefs = bpy.context.preferences
    repo = next(repo for repo in prefs.extensions.repos if repo.module == "user_default")
    isolated_root = Path(os.environ["BLENDER_USER_RESOURCES"]).resolve()
    repo_directory = Path(repo.directory).resolve()
    assert repo_directory.is_relative_to(isolated_root), repo_directory
    assert not (repo_directory / "spline_maker").exists(), "Use a fresh test directory"

    module_name = f"bl_ext.{repo.module}.spline_maker"
    menu = bpy.types.VIEW3D_MT_curve_add
    assert bpy.ops.extensions.package_install_files(
        filepath=str(archive), repo=repo.module, enable_on_install=True
    ) == {"FINISHED"}
    module = importlib.import_module(module_name)

    assert_enabled(module, menu)
    assert_probe(module.feasibility)
    assert_drawing_probe(module.drawing_probe, module.feasibility)
    assert bpy.ops.preferences.addon_disable(module=module_name) == {"FINISHED"}
    assert_disabled(module, menu)
    assert bpy.ops.preferences.addon_enable(module=module_name) == {"FINISHED"}
    assert_enabled(module, menu)
    assert bpy.ops.preferences.addon_disable(module=module_name) == {"FINISHED"}
    assert_disabled(module, menu)
    print(f"Spline Maker registration smoke test passed on {bpy.app.version_string}")


def assert_enabled(module, menu):
    assert module.__name__ in bpy.context.preferences.addons
    assert all(is_registered(cls) for cls in module.CLASSES)
    assert menu.draw._draw_funcs.count(module.ui.draw_curve_add_menu) == 1
    keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
    for tool in module.feasibility.WORKSPACE_TOOLS:
        items = keymaps[tool._bl_tool.keymap[0]].keymap_items
        assert [(item.type, item.idname, item.properties.name) for item in items] == [
            (key, "wm.tool_set_by_id", module.feasibility.tool_id(mode))
            for key, mode, _ in module.feasibility.TOOLS if mode in {"SELECT", "MOVE"}
        ]
    assert {
        (item.type, item.properties.target) for item in keymaps["Curve"].keymap_items
        if item.idname == "spline_maker.switch_tangent_tool"
    } == {("E", "ROTATE"), ("R", "SCALE")}
    keyconfigs = bpy.context.window_manager.keyconfigs
    keyconfigs.update()
    merged_items = keyconfigs.user.keymaps["Curve"].keymap_items
    for key in ("E", "R"):
        first_match = next(
            item for item in merged_items
            if item.active and item.type == key and item.value == "PRESS" and not (
                item.shift or item.ctrl or item.alt or item.oskey
            )
        )
        assert first_match.idname == "spline_maker.switch_tangent_tool", first_match.idname

    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    with bpy.context.temp_override(area=area):
        before = set(bpy.data.objects)
        assert bpy.ops.spline_maker.draw_spline() == {"CANCELLED"}
        assert set(bpy.data.objects) == before


def assert_disabled(module, menu):
    assert module.__name__ not in bpy.context.preferences.addons
    assert not any(is_registered(cls) for cls in module.CLASSES)
    assert module.ui.draw_curve_add_menu not in menu.draw._draw_funcs
    assert all(not hasattr(tool, "_bl_tool") for tool in module.feasibility.WORKSPACE_TOOLS)
    assert not hasattr(module.drawing_probe.SplineMakerDrawTool, "_bl_tool")
    assert module.drawing_probe._exit_binding is None
    keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
    assert not any("Spline Maker" in keymap.name for keymap in keymaps)
    assert not any(item.idname == "spline_maker.switch_tangent_tool"
                   for item in keymaps["Curve"].keymap_items)


def assert_drawing_probe(probe, editing):
    from bl_ui.space_toolsystem_common import ToolSelectPanelHelper

    right_click = SimpleNamespace(type="RIGHTMOUSE", alt=False, ctrl=False, shift=False, oskey=False)
    assert probe.is_finish_press(right_click)
    right_click.alt = True
    assert not probe.is_finish_press(right_click)
    assert_view_projection(probe)

    toolbar = ToolSelectPanelHelper._tool_class_from_space_type("VIEW_3D")
    add_group = next(
        group for group in toolbar._tools["OBJECT"] if isinstance(group, tuple)
        and any(getattr(tool, "idname", "") == "builtin.primitive_cube_add" for tool in group)
    )
    assert sum(getattr(tool, "idname", "") == probe.SplineMakerDrawTool.bl_idname
               for tool in add_group) == 1
    assert probe.SplineMakerDrawTool._bl_tool.cursor == "CROSSHAIR"
    keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
    binding = keymaps[probe.SplineMakerDrawTool._bl_tool.keymap[0]].keymap_items[0]
    assert binding.type == "LEFTMOUSE" and binding.properties.place_on_invoke
    keyconfigs = bpy.context.window_manager.keyconfigs
    keyconfigs.update()
    exit_binding = next(
        item for item in keyconfigs.user.keymaps["Object Mode"].keymap_items
        if item.active and item.type == "RIGHTMOUSE" and item.value == "PRESS"
        and not (item.alt or item.ctrl or item.shift or item.oskey)
    )
    assert exit_binding.idname == "spline_maker.exit_draw_tool"
    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.wm.tool_set_by_id(name="builtin.select_box") == {"FINISHED"}
        assert not bpy.ops.spline_maker.exit_draw_tool.poll()
        assert bpy.ops.wm.tool_set_by_id(name=probe.SplineMakerDrawTool.bl_idname) == {"FINISHED"}
        assert bpy.ops.spline_maker.exit_draw_tool() == {"FINISHED"}
        assert bpy.context.workspace.tools.from_space_view3d_mode("OBJECT").idname == "builtin.select_box"

    rotation = Quaternion((1, 0, 0), radians(37))
    origin = Vector((1, 2, 3))
    plane = probe.DrawingPlane(origin, rotation)
    point = Vector((2, -1, 0))
    world_point = plane.to_world(point)
    assert (plane.intersect(world_point + 8 * plane.normal, -plane.normal, perspective=False)
            - point).length < 1e-5
    oblique = (rotation @ Vector((1, 0, -2))).normalized()
    assert (plane.intersect(world_point - 6 * oblique, oblique, perspective=True)
            - point).length < 1e-5
    assert plane.intersect(world_point + 6 * oblique, oblique, perspective=True) is None
    assert plane.intersect(world_point, rotation @ Vector((1, 0, 0)), perspective=False) is None

    session = probe.DrawingSession(plane)
    before = set(bpy.data.objects)
    session.place(point)
    session.place(point)
    assert session.points == [point]
    session.place(Vector((4, 0, 0)))
    session.undo_point()
    assert session.points == [point]
    session.cancel()
    assert not session.points and set(bpy.data.objects) == before

    session.place(point)
    second = Vector((3, 2, 0))
    session.place(second)
    obj = probe.commit_curve(bpy.context, session)
    bpy.context.view_layer.update()
    spline = obj.data.splines[0]
    assert spline.type == "BEZIER"
    assert len(spline.bezier_points) == 2
    for control, local in zip(spline.bezier_points, (point, second)):
        assert (obj.matrix_world @ control.co - plane.to_world(local)).length < 1e-5
    assert bpy.context.view_layer.objects.active == obj

    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
        try:
            bpy.ops.curve.select_all(action="DESELECT")
            anchor, neighbor = obj.data.splines[0].bezier_points
            anchor.select_control_point = True
            location = anchor.co.copy()
            right = anchor.handle_right - location
            assert right.length > 0 and anchor.handle_right_type == "VECTOR"
            assert bpy.ops.wm.tool_set_by_id(name=editing.tool_id("MOVE")) == {"FINISHED"}
            assert editing.VIEW3D_GGT_spline_maker_move.poll(bpy.context)
            assert bpy.ops.spline_maker.switch_tangent_tool(target="ROTATE") == {"FINISHED"}
            assert editing.VIEW3D_GGT_spline_maker_tangent.poll(bpy.context)
            assert bpy.ops.spline_maker.tangent_step() == {"FINISHED"}
            rotated = Matrix.Rotation(radians(15), 3, "Z") @ right
            assert (anchor.handle_right - location - rotated).length < 1e-5
            assert anchor.handle_right_type == "FREE"
            assert neighbor.handle_left_type == "VECTOR"
            assert bpy.ops.spline_maker.switch_tangent_tool(target="SCALE") == {"FINISHED"}
            assert bpy.ops.spline_maker.tangent_step() == {"FINISHED"}
            assert (anchor.handle_right - location - rotated * 1.25).length < 1e-5
            assert anchor.co == location
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")


def assert_view_projection(probe):
    region = SimpleNamespace(width=1280, height=720)
    front = Quaternion((1, 0, 0), radians(90))
    side = Quaternion((0, 0, 1), radians(90)) @ front
    angled = Quaternion((1, 1, 0), radians(33))
    cursor = Vector((4, -2, 3))
    local = Vector((1.25, -0.75, 0))
    for start in (Quaternion(), front, side, angled):
        plane = probe.DrawingPlane(cursor, start)
        world_point = plane.to_world(local)
        # Reproject the same point after orbiting away from the starting view.
        for view_rotation in (start, start @ angled):
            camera = cursor + view_rotation @ Vector((0, 0, 12))
            view_matrix = (Matrix.Translation(camera) @ view_rotation.to_matrix().to_4x4()).inverted()
            for perspective, projection in (
                (False, Matrix.Diagonal((0.15, 0.25, -1e-7, 1))),
                (True, Matrix(((1, 0, 0, 0), (0, 1.5, 0, 0),
                               (0, 0, -1.001, -0.2), (0, 0, -1, 0)))),
            ):
                view = SimpleNamespace(
                    view_matrix=view_matrix, perspective_matrix=projection @ view_matrix,
                    view_perspective="PERSP" if perspective else "ORTHO",
                    is_perspective=perspective,
                )
                pixel = view3d_utils.location_3d_to_region_2d(region, view, world_point)
                actual = probe.project_view_point(plane, region, view, pixel)
                assert actual is not None and (actual - local).length < 1e-4


def is_registered(cls):
    if issubclass(cls, bpy.types.GizmoGroup):
        return bpy.types.GizmoGroup.bl_rna_get_subclass_py(cls.bl_idname) is cls
    return cls.is_registered


def assert_probe(probe):
    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.spline_maker.add_test_curve() == {"FINISHED"}
        obj = bpy.context.object
        assert obj.type == "CURVE"
        assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
        try:
            bpy.ops.curve.select_all(action="DESELECT")
            point, neighbor = obj.data.splines[0].bezier_points
            anchor = point.co.copy()
            left, right = point.handle_left.copy(), point.handle_right.copy()
            neighbor_right = neighbor.handle_right.copy()
            point.select_control_point = True
            assert bpy.ops.wm.tool_set_by_id(name="builtin.select_box") == {"FINISHED"}
            assert not bpy.ops.spline_maker.switch_tangent_tool.poll()
            for mode in ("SELECT", "MOVE", "ROTATE", "SCALE"):
                if mode in {"ROTATE", "SCALE"}:
                    assert bpy.ops.spline_maker.switch_tangent_tool(target=mode) == {"FINISHED"}
                else:
                    assert bpy.ops.wm.tool_set_by_id(name=probe.tool_id(mode)) == {"FINISHED"}
                assert probe.active_mode(bpy.context) == mode
                assert point.select_control_point
                assert probe.VIEW3D_GGT_spline_maker_tangent.poll(bpy.context) == (
                    mode in {"ROTATE", "SCALE"}
                )
                assert probe.VIEW3D_GGT_spline_maker_move.poll(bpy.context) == (mode == "MOVE")
                if mode == "ROTATE":
                    assert bpy.ops.spline_maker.tangent_step() == {"FINISHED"}
                    rotation = Matrix.Rotation(radians(15), 3, "Z")
                    assert (point.handle_left - (anchor + rotation @ (left - anchor))).length < 1e-5
                    assert (point.handle_right - (anchor + rotation @ (right - anchor))).length < 1e-5
            rotated_left, rotated_right = point.handle_left.copy(), point.handle_right.copy()
            point.select_control_point = False
            point.select_left_handle = True
            assert bpy.ops.spline_maker.tangent_step() == {"FINISHED"}
            expected_left = anchor + (rotated_left - anchor) * 1.25
            assert (point.handle_left - expected_left).length < 1e-5
            assert point.handle_right == rotated_right
            assert point.co == anchor and neighbor.handle_right == neighbor_right
            for mode in ("SELECT", "MOVE", "ROTATE", "SCALE"):
                assert bpy.ops.wm.tool_set_by_id(
                    "EXEC_REGION_WIN", name=probe.tool_id(mode), space_type="VIEW_3D"
                ) == {"FINISHED"}
                assert probe.active_mode(bpy.context) == mode
                assert point.select_left_handle
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
        assert (obj.data.splines[0].bezier_points[0].handle_left - expected_left).length < 1e-5


if __name__ == "__main__":
    main(Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True))
