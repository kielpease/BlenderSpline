"""Install a local package and check the enable, disable, re-enable cycle."""

import importlib
from math import cos, radians, sin
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
    assert_vertex_selection(module.vertex_selection, module.feasibility)
    assert_vertex_types(module.vertex_types, module.feasibility)
    assert_tangent_transforms(module.tangent_drag, module.feasibility)
    assert_tool_switching(module.feasibility)
    assert_edit_interactions(module.edit_drag, module.vertex_selection, module.feasibility)
    sys.path.insert(0, str(Path(__file__).parent))
    from segment_checks import run as check_segments
    check_segments(module)
    from region_checks import run as check_regions
    check_regions(module)
    from control_checks import run as check_controls
    check_controls(module)
    from whole_move_checks import run as check_whole_move
    check_whole_move(module)
    assert_finish_edit(module)
    assert_enter_edit(module)
    assert_object_display(module)
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
    assert bpy.context.window_manager.spline_maker_selection_level == "VERTEX"
    for name in ("Curve", "3D View"):
        assert {(item.type, item.value) for item in keymaps[name].keymap_items
                if item.idname == "spline_maker.exit_edit_shortcut"} == {("ESC", "PRESS"), ("FOUR", "PRESS")}
        assert {(item.type, item.properties.target) for item in keymaps[name].keymap_items
                if item.idname in {"spline_maker.selection_level", "spline_maker.enter_selection_level"}} == {("ONE", "VERTEX"), ("TWO", "SEGMENT"), ("THREE", "REGION")}
        assert not any(item.type == "FIVE" and item.idname.startswith("spline_maker.")
                       for item in keymaps[name].keymap_items)
        assert {(item.type, item.properties.target) for item in keymaps[name].keymap_items
                if item.idname == "spline_maker.enter_selection_level"} == {("ONE", "VERTEX"), ("TWO", "SEGMENT"), ("THREE", "REGION")}
    for name in ("Object Mode", "Curve", "3D View"):
        assert [(item.type, item.value) for item in keymaps[name].keymap_items
                if item.idname == "spline_maker.enter_edit"] == [("SIX", "PRESS")]
    for tool in module.feasibility.WORKSPACE_TOOLS:
        assert tool.bl_widget == "VIEW3D_GGT_spline_maker_transform"
        items = keymaps[tool._bl_tool.keymap[0]].keymap_items
        assert [(item.type, item.idname, item.properties.target) for item in items] == [
            (key, "spline_maker.tool_shortcut", mode)
            for key, mode, _ in module.feasibility.TOOLS
        ]
    assert {
        (item.type, item.properties.target) for item in keymaps["Curve"].keymap_items
        if item.idname == "spline_maker.tool_shortcut"
    } == {(key, mode) for key, mode, _ in module.feasibility.TOOLS}
    assert {
        (item.type, item.properties.target) for item in keymaps["3D View"].keymap_items
        if item.idname == "spline_maker.tool_shortcut"
    } == {(key, mode) for key, mode, _ in module.feasibility.TOOLS}
    assert {
        (item.type, item.value, item.shift) for item in keymaps["Curve"].keymap_items
        if item.idname == "spline_maker.vertex_select"
    } == {("LEFTMOUSE", "PRESS", 0), ("LEFTMOUSE", "PRESS", 1)}
    assert {
        (item.type, item.value) for item in keymaps["Curve"].keymap_items
        if item.idname == "spline_maker.vertex_context_menu"
    } == {("RIGHTMOUSE", "PRESS")}
    keyconfigs = bpy.context.window_manager.keyconfigs
    keyconfigs.update()
    merged_items = keyconfigs.user.keymaps["Curve"].keymap_items
    right_click = next(item for item in merged_items
                       if item.active and item.type == "RIGHTMOUSE" and item.value == "PRESS"
                       and not (item.shift or item.ctrl or item.alt or item.oskey))
    assert right_click.idname == "spline_maker.vertex_context_menu"
    for key in ("Q", "W", "E", "R"):
        first_match = next(
            item for item in merged_items
            if item.active and item.type == key and item.value == "PRESS" and not (
                item.shift or item.ctrl or item.alt or item.oskey
            )
        )
        assert first_match.idname == "spline_maker.tool_shortcut", first_match.idname

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
    assert not module.vertex_selection._bindings
    assert module.vertex_selection._cursor_handler is None
    assert not module.vertex_types._bindings
    assert module.edit_drag._active is None
    assert module.vertex_selection._gesture is None
    assert not module.transform_gizmos._groups
    assert not module.segment_selection._bindings
    assert not module.feasibility._curve_shortcuts
    assert not hasattr(bpy.types.WindowManager, "spline_maker_selection_level")
    assert not hasattr(bpy.types.WindowManager, "spline_maker_curve_color")
    assert not hasattr(bpy.types.WindowManager, "spline_maker_bright_curves")
    assert module.display._handler is None
    keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
    assert not any("Spline Maker" in keymap.name for keymap in keymaps)
    assert not any(item.idname == "spline_maker.tool_shortcut"
                   for item in keymaps["Curve"].keymap_items)
    assert not any(item.idname == "spline_maker.tool_shortcut"
                   for item in keymaps["3D View"].keymap_items)
    assert not any(item.idname == "spline_maker.vertex_context_menu"
                   for item in keymaps["Curve"].keymap_items)
    for name in ("Curve", "3D View"):
        assert not any(item.idname == "spline_maker.exit_edit_shortcut" for item in keymaps[name].keymap_items)
    for name in ("Object Mode", "Curve", "3D View"):
        assert not any(item.idname == "spline_maker.enter_edit" for item in keymaps[name].keymap_items)


def assert_enter_edit(module):
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.object.select_all(action="DESELECT")
        assert not bpy.ops.spline_maker.enter_edit.poll()
        bpy.ops.mesh.primitive_cube_add()
        mesh = bpy.context.object
        assert not bpy.ops.spline_maker.enter_edit.poll()
        bpy.ops.object.mode_set(mode="EDIT")
        assert not bpy.ops.spline_maker.enter_edit.poll()
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.spline_maker.add_test_curve()
        obj = bpy.context.object
        mesh.select_set(True)
        assert not bpy.ops.spline_maker.enter_edit.poll()
        mesh.select_set(False)
        poly = obj.data.splines.new("POLY")
        assert not bpy.ops.spline_maker.enter_edit.poll()
        obj.data.splines.remove(poly)
        before = [module.edit_drag.snapshot(p) for p in obj.data.splines[0].bezier_points]
        objects = set(bpy.data.objects.keys())
        for _ in range(2):
            assert bpy.ops.spline_maker.enter_edit.poll()
            assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
            assert bpy.context.mode == "EDIT_CURVE" and bpy.context.edit_object == obj
            assert module.feasibility.active_mode(bpy.context) == "SELECT"
            assert module.segment_selection.level(bpy.context) == "VERTEX"
            # 6 also enters vertex editing from a native tool or another level.
            bpy.ops.spline_maker.selection_level(target="WHOLE")
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
            assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
            assert module.feasibility.active_mode(bpy.context) == "SELECT"
            assert module.segment_selection.level(bpy.context) == "VERTEX"
            assert bpy.ops.spline_maker.exit_edit_shortcut() == {"FINISHED"}
            assert bpy.context.mode == "OBJECT" and bpy.context.object == obj and obj.select_get()
            assert [module.edit_drag.snapshot(p) for p in obj.data.splines[0].bezier_points] == before
            assert set(bpy.data.objects.keys()) == objects
        print("6 Edit Spline entry/exit and unsupported-context guards passed")


def assert_finish_edit(module):
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.spline_maker.add_test_curve()
        obj = bpy.context.object
        points = obj.data.splines[0].bezier_points
        points.add(1)
        obj.data.splines[0].use_cyclic_u = True
        for p, co in zip(points, ((-2, -1, 0), (2, -1, 0), (0, 2, 0))):
            p.co = co
            p.handle_left_type = p.handle_right_type = "FREE"
            p.handle_left = p.handle_right = p.co
        original_name = obj.name
        before_objects = set(bpy.data.objects.keys())
        before = [module.edit_drag.snapshot(p) for p in points]
        for level in ("VERTEX", "SEGMENT", "REGION", "WHOLE"):
            for index, (_, mode, _) in enumerate(module.feasibility.TOOLS):
                assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
                bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
                assert not bpy.ops.spline_maker.exit_edit_shortcut.poll()
                assert bpy.ops.spline_maker.finish_edit.poll()
                bpy.ops.spline_maker.switch_tangent_tool(target=mode)
                bpy.ops.spline_maker.selection_level(target=level)
                assert bpy.ops.spline_maker.exit_edit_shortcut.poll()
                result = (bpy.ops.spline_maker.finish_edit() if index % 2 == 0
                          else bpy.ops.spline_maker.exit_edit_shortcut())
                assert result == {"FINISHED"} and bpy.context.mode == "OBJECT"
                assert bpy.context.object.name == original_name and bpy.context.object.select_get()
                assert set(bpy.data.objects.keys()) == before_objects
                assert [module.edit_drag.snapshot(p) for p in bpy.context.object.data.splines[0].bezier_points] == before
                for workspace_mode in ("OBJECT", "EDIT_CURVE"):
                    assert bpy.context.workspace.tools.from_space_view3d_mode(workspace_mode).idname == "builtin.select_box"
                assert bpy.context.window_manager.spline_maker_selection_level == "VERTEX"
                assert not bpy.ops.spline_maker.exit_edit_shortcut.poll()
                assert not bpy.ops.spline_maker.finish_edit.poll()
                assert module.vertex_selection._gesture is None
                assert module.edit_drag._active is None and module.tangent_drag._active is None
        print("Finish Editing passed from Q/W/E/R and all four selection levels")


def assert_object_display(module):
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.spline_maker.add_test_curve()
        obj = bpy.context.object
        obj.select_set(False)
        bpy.context.view_layer.update()
        assert module.display.active(bpy.context)
        assert obj in module.display.object_curves(bpy.context)
        obj.hide_set(True)
        bpy.context.view_layer.update()
        assert obj not in module.display.object_curves(bpy.context)
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.update()
        assert obj not in module.display.object_curves(bpy.context)
        # Hidden edit control points still contribute to the Object Mode curve.
        point = obj.data.splines[0].bezier_points[0]
        point.hide = True
        project = lambda p: (p.x, p.y)
        assert not module.segment_selection.projected_segments(obj.data, obj.matrix_world, project)[0:1]
        projected = module.segment_selection.projected_segments(obj.data, obj.matrix_world, project, include_hidden=True)
        assert len(projected) == 1 and projected[0][1]
        point.hide = False


def assert_vertex_types(types, editing):
    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.spline_maker.add_test_curve() == {"FINISHED"}
        obj = bpy.context.object
        spline = obj.data.splines[0]
        spline.bezier_points.add(1)
        first, middle, last = spline.bezier_points
        for point, co in zip((first, middle, last), ((-3, 0, 0), (0, 2, 0), (4, 0, 0))):
            point.co = co
            point.handle_left_type = point.handle_right_type = "FREE"
            point.handle_left = point.co + Vector((-0.8, -0.3, 0))
            point.handle_right = point.co + Vector((1.2, 0.8, 0))
        assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
        bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
        try:
            assert bpy.ops.wm.tool_set_by_id(name="builtin.select_box") == {"FINISHED"}
            assert not bpy.ops.spline_maker.vertex_type.poll()
            assert not bpy.ops.spline_maker.vertex_context_menu.poll()
            for mode in ("SELECT", "MOVE", "ROTATE", "SCALE"):
                assert bpy.ops.wm.tool_set_by_id(name=editing.tool_id(mode)) == {"FINISHED"}
                assert bpy.ops.spline_maker.vertex_context_menu.poll()
            bpy.ops.curve.select_all(action="DESELECT")
            assert not bpy.ops.spline_maker.vertex_type.poll()
            spline = obj.data.splines[0]
            first, middle, last = spline.bezier_points
            anchors = [p.co.copy() for p in spline.bezier_points]
            original_last = (last.handle_left.copy(), last.handle_right.copy())
            first.select_control_point = True
            middle.select_right_handle = True
            assert bpy.ops.wm.tool_set_by_id(name=editing.tool_id("SELECT")) == {"FINISHED"}
            selection = [tuple(getattr(p, f) for f in types.SELECTION_FLAGS) for p in spline.bezier_points]
            for identifier, expected in (("BEZIER", "ALIGNED"), ("BEZIER_CORNER", "FREE"),
                                         ("CORNER", "VECTOR"), ("SMOOTH", "AUTO")):
                lengths = [(p.handle_left - p.co).length for p in (first, middle)]
                right_lengths = [(p.handle_right - p.co).length for p in (first, middle)]
                coordinates = [(p.handle_left.copy(), p.handle_right.copy()) for p in (first, middle)]
                assert bpy.ops.spline_maker.vertex_type(vertex_type=identifier) == {"FINISHED"}
                assert all(p.handle_left_type == p.handle_right_type == expected for p in (first, middle))
                assert len(obj.data.splines) == 1 and len(spline.bezier_points) == 3
                assert not spline.use_cyclic_u
                assert all(p.co == co for p, co in zip(spline.bezier_points, anchors))
                assert [tuple(getattr(p, f) for f in types.SELECTION_FLAGS) for p in spline.bezier_points] == selection
                assert (last.handle_left, last.handle_right) == original_last
                if expected == "ALIGNED":
                    for i, p in enumerate((first, middle)):
                        left, right = p.handle_left - p.co, p.handle_right - p.co
                        assert left.cross(right).length < 1e-5 and left.dot(right) < 0
                        assert abs(left.length - lengths[i]) < 1e-5
                        assert abs(right.length - right_lengths[i]) < 1e-5
                if expected == "FREE":
                    assert [(p.handle_left, p.handle_right) for p in (first, middle)] == coordinates
            # Independent tangent editing must preserve the other handle and topology.
            bpy.ops.spline_maker.vertex_type(vertex_type="BEZIER_CORNER")
            left = middle.handle_left.copy()
            middle.handle_right += Vector((0, 0.5, 0))
            obj.data.update_tag()
            assert middle.handle_left == left and len(spline.bezier_points) == 3
            # Hidden selected vertices must remain untouched.
            last.hide = True
            last.select_control_point = True
            bpy.ops.spline_maker.vertex_type(vertex_type="CORNER")
            assert last.handle_left_type == last.handle_right_type == "FREE"
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")


def assert_tool_switching(editing):
    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.spline_maker.add_test_curve()
        obj = bpy.context.object
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
        try:
            bpy.ops.curve.select_all(action="DESELECT")
            first = obj.data.splines[0].bezier_points[0]
            first.select_left_handle = True
            geometry = [(p.co.copy(), p.handle_left.copy(), p.handle_right.copy())
                        for p in obj.data.splines[0].bezier_points]
            bpy.ops.wm.tool_set_by_id(name="builtin.move")
            assert not bpy.ops.spline_maker.tool_shortcut.poll()
            assert bpy.ops.spline_maker.switch_tangent_tool(target="SELECT") == {"FINISHED"}
            for _, start, _ in editing.TOOLS:
                for _, target, _ in editing.TOOLS:
                    bpy.ops.spline_maker.switch_tangent_tool(target=start)
                    assert bpy.ops.spline_maker.tool_shortcut(target=target) == {"FINISHED"}
                    assert editing.active_mode(bpy.context) == target
                    assert first.select_left_handle and not first.select_right_handle
                    assert not first.select_control_point
                    assert bpy.ops.spline_maker.switch_tangent_tool(
                        "EXEC_REGION_WIN", target=target,
                    ) == {"FINISHED"}
                    assert editing.active_mode(bpy.context) == target
                    assert [(p.co, p.handle_left, p.handle_right)
                            for p in obj.data.splines[0].bezier_points] == geometry
            # Industry Compatible binds native Q/W/E/R in 3D View. Verify the
            # merged priority using the installed preset, then restore config.
            previous = bpy.context.window_manager.keyconfigs.active.name
            preset = next(Path(path) / "Industry_Compatible.py"
                          for path in bpy.utils.preset_paths("keyconfig")
                          if (Path(path) / "Industry_Compatible.py").exists())
            try:
                assert bpy.utils.keyconfig_set(str(preset))
                keyconfigs = bpy.context.window_manager.keyconfigs
                keyconfigs.update()
                for name in ("Object Mode", "Curve", "3D View"):
                    match = next(item for item in keyconfigs.user.keymaps[name].keymap_items
                                 if item.active and item.type == "SIX" and item.value == "PRESS"
                                 and not (item.shift or item.ctrl or item.alt or item.oskey))
                    assert match.idname == "spline_maker.enter_edit", (name, match.idname)
                for name in ("Curve", "3D View"):
                    items = keyconfigs.user.keymaps[name].keymap_items
                    for key, _, _ in editing.TOOLS:
                        match = next(item for item in items
                                     if item.active and item.type == key and item.value == "PRESS"
                                     and not (item.shift or item.ctrl or item.alt or item.oskey))
                        assert match.idname == "spline_maker.tool_shortcut", (name, key, match.idname)
                    for key in ("ONE", "TWO", "THREE"):
                        match = next(item for item in items if item.active and item.type == key
                                     and item.value == "PRESS"
                                     and not (item.shift or item.ctrl or item.alt or item.oskey))
                        assert match.idname == "spline_maker.enter_selection_level"
            finally:
                bpy.context.window_manager.keyconfigs.active = bpy.context.window_manager.keyconfigs[previous]
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")


def assert_tangent_transforms(drag, editing):
    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.spline_maker.add_test_curve()
        obj = bpy.context.object
        obj.scale = (2, 0.5, 1)
        obj.rotation_euler.z = 0.4
        bpy.context.view_layer.update()
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
        try:
            bpy.ops.wm.tool_set_by_id(name=editing.tool_id("ROTATE"))
            first, second = obj.data.splines[0].bezier_points
            for handle_type in ("VECTOR", "AUTO", "ALIGNED", "FREE"):
                bpy.ops.curve.select_all(action="DESELECT")
                first.handle_left_type = first.handle_right_type = handle_type
                first.select_right_handle = True
                assert editing.selected_handles(bpy.context) == [(first, "right")]
                assert not bpy.ops.spline_maker.tangent_step.poll()
                assert not bpy.ops.spline_maker.tangent_drag.poll()
                first.select_control_point = True
                assert bpy.ops.spline_maker.tangent_step.poll()
                assert bpy.ops.spline_maker.tangent_drag.poll()
                snapshot = drag.capture(bpy.context)
                anchor, left, right = first.co.copy(), first.handle_left.copy(), first.handle_right.copy()
                neighbor = (second.co.copy(), second.handle_left.copy(), second.handle_right.copy())
                world = obj.matrix_world.to_3x3()
                matrix = world.inverted() @ Matrix.Rotation(0.6, 3, "Z") @ world
                drag.apply(obj.data, snapshot, matrix, rotating=True)
                assert first.co == anchor
                assert (first.handle_right - anchor - matrix @ (right - anchor)).length < 1e-5
                if handle_type in {"AUTO", "ALIGNED"}:
                    assert first.handle_left_type == first.handle_right_type == "ALIGNED"
                    assert (first.handle_left - anchor - matrix @ (left - anchor)).length < 1e-5
                else:
                    assert first.handle_left_type == first.handle_right_type == "FREE"
                    assert (first.handle_left - anchor - matrix @ (left - anchor)).length < 1e-5
                # Updates use a fixed snapshot, so mouse events cannot compound.
                drag.apply(obj.data, snapshot, matrix, rotating=True)
                assert (first.handle_right - anchor - matrix @ (right - anchor)).length < 1e-5
                drag.restore(obj.data, snapshot)
                assert first.handle_left_type == first.handle_right_type == handle_type
                assert (first.handle_left - left).length < 1e-5
                assert (first.handle_right - right).length < 1e-5
                drag.apply(obj.data, snapshot, Matrix.Scale(1.4, 3), rotating=False)
                assert (first.handle_right - anchor - 1.4 * (right - anchor)).length < 1e-5
                assert (first.handle_left - anchor - 1.4 * (left - anchor)).length < 1e-5
                assert first.co == anchor and first.select_control_point
                assert (second.co, second.handle_left, second.handle_right) == neighbor
                drag.restore(obj.data, snapshot)
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")


def assert_vertex_selection(picking, editing):
    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.spline_maker.add_test_curve() == {"FINISHED"}
        obj = bpy.context.object
        obj.location = (4, -3, 1)
        obj.rotation_euler.z = radians(32)
        obj.scale = (1.5, 0.75, 2.0)
        bpy.context.view_layer.update()
        assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
        bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
        try:
            assert bpy.ops.wm.tool_set_by_id(name="builtin.select_box") == {"FINISHED"}
            assert not bpy.ops.spline_maker.vertex_select.poll()
            assert bpy.ops.wm.tool_set_by_id(name=editing.tool_id("SELECT")) == {"FINISHED"}
            assert bpy.ops.spline_maker.vertex_select.poll()
            points = tuple(editing.editable_bezier_points(bpy.context))
            first, second = points
            picking.clear_selection(points)
            for zoom in (20, 75):
                def project(world):
                    return 480 + world.x * zoom, 360 + world.y * zoom

                components = list(picking.project_components(points, obj.matrix_world, project, "ALL"))
                assert len(components) == 6
                anchor_pixel = project(obj.matrix_world @ first.co)
                handle_pixel = project(obj.matrix_world @ first.handle_left)
                anchor = picking.pick_component(components, anchor_pixel)
                handle = picking.pick_component(components, handle_pixel)
                assert anchor.coordinate == "co" and handle.coordinate == "handle_left"
                assert picking.pick_component(components, (0, 0)) is None

                picking.click_select(points, anchor, extend=False)
                assert first.select_control_point and not first.select_left_handle
                picking.click_select(points, handle, extend=False)
                assert not first.select_control_point and first.select_left_handle
                picking.click_select(points, anchor, extend=True)
                picking.click_select(points, handle, extend=True)
                assert first.select_control_point and not first.select_left_handle
                picking.click_select(points, None, extend=False)
                assert not any(component.selected for component in components)

                # The box includes the handle, but only its anchor is selected.
                xmin, xmax = sorted((anchor_pixel[0], handle_pixel[0]))
                ymin, ymax = sorted((anchor_pixel[1], handle_pixel[1]))
                picking.box_select(points, components, (xmax + 1, ymax + 1),
                                   (xmin - 1, ymin - 1), extend=False)
                assert first.select_control_point and not first.select_left_handle
                assert not second.select_control_point
                second_pixel = project(obj.matrix_world @ second.co)
                x, y = second_pixel
                picking.box_select(points, components, (x - 1, y - 1), (x + 1, y + 1), extend=True)
                assert first.select_control_point and second.select_control_point

                first.hide = True
                visible = tuple(editing.editable_bezier_points(bpy.context))
                assert len(visible) == 1 and visible[0].co == second.co
                assert len(list(picking.project_components(visible, obj.matrix_world, project, "NONE"))) == 1
                first.hide = False

            assert bpy.ops.wm.tool_set_by_id(name=editing.tool_id("MOVE")) == {"FINISHED"}
            assert bpy.ops.spline_maker.vertex_select.poll()
            assert (editing.active_mode(bpy.context) == "MOVE" and editing.move_origin(bpy.context) is not None)
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")


def assert_edit_interactions(drag, picking, editing):
    """Native data and synthetic modal events; this does not test UI dispatch."""
    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.spline_maker.add_test_curve()
        obj = bpy.context.object
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
        first, second = obj.data.splines[0].bezier_points
        fake = SimpleNamespace(
            mode="EDIT_CURVE", edit_object=obj, objects_in_mode=[obj], workspace=bpy.context.workspace,
            window=bpy.context.window,
            area=SimpleNamespace(type="VIEW_3D", regions=[], tag_redraw=lambda: None,
                                 header_text_set=lambda _: None, as_pointer=lambda: 11),
            region=SimpleNamespace(type="WINDOW", x=0, y=0, width=1000, height=700, as_pointer=lambda: 12),
            region_data=SimpleNamespace(view_rotation=Quaternion(),
                view_matrix=Matrix.Translation((0, 0, -10)),
                perspective_matrix=Matrix.Diagonal((0.1, 0.1, -0.01, 1)),
                is_perspective=False, view_perspective="ORTHO"),
            space_data=SimpleNamespace(overlay=SimpleNamespace(show_overlays=True)),
            window_manager=SimpleNamespace(modal_handler_add=lambda _: None),
        )

        def event(kind, pixel, value="PRESS"):
            return SimpleNamespace(type=kind, value=value, mouse_x=pixel[0], mouse_y=pixel[1],
                                   mouse_region_x=pixel[0], mouse_region_y=pixel[1],
                                   shift=False, ctrl=False, alt=False)

        def gesture():
            operator = SimpleNamespace()
            cls = picking.SPLINE_MAKER_OT_vertex_select
            operator.cleanup = lambda ctx: cls.cleanup(operator, ctx)
            operator.cancel = lambda ctx: cls.cancel(operator, ctx)
            return operator, cls

        def geometry():
            return [drag.snapshot(point) for point in (first, second)]

        try:
            for _, mode, _ in editing.TOOLS:
                bpy.ops.spline_maker.switch_tangent_tool(target=mode)
                assert bpy.ops.spline_maker.vertex_select.poll()
                before = geometry()
                op, cls = gesture()
                assert cls.invoke(op, fake, event("LEFTMOUSE", (250, 200))) == {"RUNNING_MODAL"}
                assert cls.modal(op, fake, event("LEFTMOUSE", (650, 500), "RELEASE")) == {"FINISHED"}
                assert first.select_control_point and second.select_control_point
                assert geometry() == before and editing.active_mode(bpy.context) == mode
                # An actual handle hit takes precedence over a marquee in every mode.
                picking.clear_selection((first, second))
                second.select_control_point = True
                initial_selection = [(p.select_control_point, p.select_left_handle, p.select_right_handle)
                                     for p in (first, second)]
                component = next(c for c in picking.viewport_components(fake)
                                 if c.point == first and c.coordinate == "handle_right")
                start = component.pixel
                end = (start[0] + 40, start[1] + 25)
                op, cls = gesture()
                cls.invoke(op, fake, event("LEFTMOUSE", start))
                assert cls.modal(op, fake, event("MOUSEMOVE", end, "NOTHING")) == {"RUNNING_MODAL"}
                assert op.handle_moved and first.co == before[0][0]
                assert first.handle_right != before[0][2] and drag.snapshot(second) == before[1]
                assert cls.modal(op, fake, event("ESC", end)) == {"CANCELLED"}
                assert geometry() == before
                assert [(p.select_control_point, p.select_left_handle, p.select_right_handle)
                        for p in (first, second)] == initial_selection
                assert picking._gesture is None

            for handle_type in ("FREE", "ALIGNED", "AUTO", "VECTOR"):
                first.handle_left_type = first.handle_right_type = handle_type
                state = drag.snapshot(first)
                delta = Vector((0.5, 0.7, 0))
                for _ in range(2):
                    drag.translate_handle(first, state, "handle_right", delta)
                    assert first.co == state[0]
                    assert (first.handle_right - state[2] - delta).length < 1e-5
                    if handle_type in {"AUTO", "ALIGNED"}:
                        left, right = first.handle_left - first.co, first.handle_right - first.co
                        assert left.cross(right).length < 1e-5 and left.dot(right) < 0
                        assert abs(left.length - (state[1] - state[0]).length) < 1e-5
                        assert first.handle_left_type == first.handle_right_type == "ALIGNED"
                    else:
                        assert first.handle_left == state[1]
                        assert first.handle_left_type == first.handle_right_type == "FREE"
                drag.restore(first, state)
                assert drag.snapshot(first) == state

            # Simulate axis/plane Move on real curve data after object transforms.
            obj.rotation_euler.z = 0.4
            obj.scale = (2, 0.5, 1)
            bpy.context.view_layer.update()
            bpy.ops.spline_maker.switch_tangent_tool(target="MOVE")
            picking.clear_selection((first, second))
            first.select_control_point = second.select_control_point = True
            for axis in ("X", "Y", "XY", "VIEW"):
                before = geometry()
                cls = drag.SPLINE_MAKER_OT_move_drag
                op = SimpleNamespace(axis=axis, report=lambda *_: None)
                op.update = lambda ctx, evt: cls.update(op, ctx, evt)
                op.finish = lambda ctx, **kwargs: cls.finish(op, ctx, **kwargs)
                assert cls.invoke(op, fake, event("LEFTMOUSE", (500, 350))) == {"RUNNING_MODAL"}
                assert cls.modal(op, fake, event("MOUSEMOVE", (560, 400), "NOTHING")) == {"RUNNING_MODAL"}
                world_delta = obj.matrix_world.to_3x3() @ (first.co - before[0][0])
                assert world_delta.length > 0.1 and abs(world_delta.z) < 1e-5
                if axis == "X":
                    assert abs(world_delta.y) < 1e-5
                elif axis == "Y":
                    assert abs(world_delta.x) < 1e-5
                else:
                    assert abs(world_delta.x) > 0.1 and abs(world_delta.y) > 0.1
                for point, state in zip((first, second), before):
                    assert (obj.matrix_world.to_3x3() @ (point.co - state[0]) - world_delta).length < 1e-5
                    assert ((point.handle_left - point.co) - (state[1] - state[0])).length < 1e-5
                assert cls.modal(op, fake, event("RIGHTMOUSE", (560, 400))) == {"CANCELLED"}
                assert geometry() == before and drag._active is None
            # An orthographic view cannot disambiguate depth-axis dragging.
            op = SimpleNamespace(axis="Z", report=lambda *_: None)
            assert drag.SPLINE_MAKER_OT_move_drag.invoke(op, fake, event("LEFTMOUSE", (500, 350))) == {"CANCELLED"}
        finally:
            picking.stop_active(fake)
            if drag._active is not None:
                drag._active.finish(fake, cancel=True)
            bpy.ops.object.mode_set(mode="OBJECT")


def assert_drawing_probe(probe, editing):
    from bl_ui.space_toolsystem_common import ToolSelectPanelHelper

    right_click = SimpleNamespace(type="RIGHTMOUSE", alt=False, ctrl=False, shift=False, oskey=False)
    assert probe.is_finish_press(right_click)
    right_click.alt = True
    assert not probe.is_finish_press(right_click)
    assert probe.button_at((100, 55)) == "Finish"
    assert probe.button_at((180, 55)) == "Cancel"
    assert probe.button_at((165, 55)) is None
    assert_view_projection(probe)
    assert_mixed_spline(probe)
    assert_shift_constraint(probe)
    assert_closing_spline(probe)

    toolbar = ToolSelectPanelHelper._tool_class_from_space_type("VIEW_3D")
    add_group = next(
        group for group in toolbar._tools["OBJECT"] if isinstance(group, tuple)
        and any(getattr(tool, "idname", "") == "builtin.primitive_cube_add" for tool in group)
    )
    assert sum(getattr(tool, "idname", "") == probe.SplineMakerDrawTool.bl_idname
               for tool in add_group) == 1
    assert probe.SplineMakerDrawTool._bl_tool.cursor == "CROSSHAIR"
    keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
    bindings = keymaps[probe.SplineMakerDrawTool._bl_tool.keymap[0]].keymap_items
    assert [(binding.type, binding.shift, binding.properties.place_on_invoke)
            for binding in bindings] == [("LEFTMOUSE", False, True), ("LEFTMOUSE", True, True)]
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
        assert bpy.ops.wm.tool_set_by_id(name=probe.SplineMakerDrawTool.bl_idname, space_type="VIEW_3D") == {"FINISHED"}
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
    existing_curves = set(bpy.data.curves)
    selection = set(bpy.context.selected_objects)
    active_object = bpy.context.view_layer.objects.active
    session.place(point)
    assert not session.can_place(point)
    assert not session.can_place(None)
    session.place(point)
    assert [vertex.anchor for vertex in session.points] == [point]
    session.place(Vector((4, 0, 0)))
    session.undo_point()
    assert [vertex.anchor for vertex in session.points] == [point]
    session.cancel()
    assert not session.points and set(bpy.data.objects) == before
    assert set(bpy.data.curves) == existing_curves
    assert set(bpy.context.selected_objects) == selection
    assert bpy.context.view_layer.objects.active == active_object

    session.place(point)
    operator = SimpleNamespace(session=session, cleanup=session.cancel, report=lambda *_: None)
    assert probe.SPLINE_MAKER_OT_draw_spline.finish(operator, bpy.context) == {"RUNNING_MODAL"}
    assert set(bpy.data.objects) == before
    second = Vector((3, 2, 0))
    session.place(second)
    session.place(second)
    assert bpy.ops.wm.tool_set_by_id(name=probe.SplineMakerDrawTool.bl_idname, space_type="VIEW_3D") == {"FINISHED"}
    assert probe.SPLINE_MAKER_OT_draw_spline.finish(operator, bpy.context) == {"FINISHED"}
    assert bpy.context.workspace.tools.from_space_view3d_mode("OBJECT").idname == "builtin.select_box"
    assert not session.points
    obj = bpy.context.view_layer.objects.active
    assert set(bpy.data.objects) - before == {obj}
    bpy.context.view_layer.update()
    spline = obj.data.splines[0]
    assert spline.type == "BEZIER"
    assert not spline.use_cyclic_u
    assert len(spline.bezier_points) == 2
    assert (obj.matrix_world.translation - plane.to_world((point + second) / 2)).length < 1e-5
    for control, local in zip(spline.bezier_points, (point, second)):
        assert (obj.matrix_world @ control.co - plane.to_world(local)).length < 1e-5
    assert bpy.context.view_layer.objects.active == obj

    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
        bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
        try:
            bpy.ops.curve.select_all(action="DESELECT")
            anchor, neighbor = obj.data.splines[0].bezier_points
            anchor.select_control_point = True
            location = anchor.co.copy()
            right = anchor.handle_right - location
            assert right.length > 0 and anchor.handle_right_type == "VECTOR"
            assert bpy.ops.wm.tool_set_by_id(name=editing.tool_id("MOVE")) == {"FINISHED"}
            assert (editing.active_mode(bpy.context) == "MOVE" and editing.move_origin(bpy.context) is not None)
            assert bpy.ops.spline_maker.switch_tangent_tool(target="ROTATE") == {"FINISHED"}
            assert bpy.ops.spline_maker.tangent_step.poll()
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


def assert_mixed_spline(probe):
    plane = probe.DrawingPlane(Vector((0, 0, 0)), Quaternion())
    session = probe.DrawingSession(plane)
    start = Vector((0, 0, 0))
    anchor = Vector((3, 0, 0))
    placement = probe.PointPlacement((100, 100), anchor)
    placement.update((102, 103), anchor + Vector((0.2, 0.3, 0)))
    assert placement.point.anchor == anchor and placement.point.tangent is None
    offset = Vector((0.75, 1.5, 0))
    placement.update((110, 115), anchor + offset)
    assert placement.point.tangent == offset

    session.place(start)
    session.place(placement.point.anchor, placement.point.tangent)
    end = Vector((8, 3, 0))
    session.place(end)
    preview = probe.segment_preview(*session.points[:2])
    assert preview[0] == start and preview[-1] == anchor
    assert any(abs(point.y) > 0.1 for point in preview[1:-1])
    obj = probe.commit_curve(bpy.context, session)
    bpy.context.view_layer.update()
    first, middle, last = obj.data.splines[0].bezier_points
    assert (obj.matrix_world.translation - (start + anchor + end) / 3).length < 1e-5
    assert first.handle_right_type == last.handle_left_type == "VECTOR"
    assert middle.handle_left_type == middle.handle_right_type == "ALIGNED"
    assert (obj.matrix_world @ middle.handle_left - (anchor - offset)).length < 1e-5
    assert (obj.matrix_world @ middle.handle_right - (anchor + offset)).length < 1e-5
    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
        bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
        try:
            bpy.ops.curve.select_all(action="DESELECT")
            middle = obj.data.splines[0].bezier_points[1]
            middle.select_control_point = True
            assert bpy.ops.wm.tool_set_by_id(name="spline_maker.probe_rotate") == {"FINISHED"}
            assert bpy.ops.spline_maker.tangent_step() == {"FINISHED"}
            rotated = Matrix.Rotation(radians(15), 3, "Z") @ offset
            assert (middle.handle_left - (middle.co - rotated)).length < 1e-5
            assert (middle.handle_right - (middle.co + rotated)).length < 1e-5
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")


def assert_shift_constraint(probe):
    plane = probe.DrawingPlane(Vector((0, 0, 0)), Quaternion())
    session = probe.DrawingSession(plane)
    previous = Vector((3, -2, 0))
    projected = Vector((6, -1, 0))
    assert session.placement_anchor(projected, snap=True) == projected
    session.place(previous)
    assert session.placement_anchor(previous, snap=True) == previous
    assert session.placement_anchor(None, snap=True) is None
    for degrees in range(-180, 180, 45):
        for delta in (-22.4, 22.4):
            angle = radians(degrees + delta)
            projected = previous + 5 * Vector((cos(angle), sin(angle), 0))
            snapped = session.placement_anchor(projected, snap=True)
            target = radians(degrees)
            expected = previous + 5 * Vector((cos(target), sin(target), 0))
            assert (snapped - expected).length < 1e-5
            assert abs((snapped - previous).length - (projected - previous).length) < 1e-5
            assert session.placement_anchor(projected, snap=False) == projected

    # A snapped anchor may be offset from the pointer. The handle follows
    # the projected drag motion when Shift is released during the drag.
    projected = Vector((6, -1, 0))
    operator = SimpleNamespace(session=session, shift=True, project=lambda *_: projected)
    probe.SPLINE_MAKER_OT_draw_spline.begin_placement(operator, None, (100, 100))
    snapped = session.placement_anchor(projected, snap=True)
    assert operator.placement.point.anchor == snapped
    operator.shift = False
    drag = Vector((0.25, 0.75, 0))
    operator.placement.update((110, 112), projected + drag)
    assert operator.placement.point.anchor == snapped
    assert (operator.placement.point.tangent - drag).length < 1e-5


def assert_closing_spline(probe):
    operator_class = probe.SPLINE_MAKER_OT_draw_spline
    plane = probe.DrawingPlane(Vector((2, 3, 4)), Quaternion((1, 0, 0), radians(33)))
    session = probe.DrawingSession(plane)
    first = Vector((0, 0, 0))
    tangent = Vector((1, 0.5, 0))
    last = Vector((2, 5, 0))
    session.place(first, tangent)
    session.place(Vector((5, 0, 0)))
    before = set(bpy.data.objects)
    hit = (200, 200)
    assert probe.near_first_vertex((206, 208), hit)
    assert not probe.near_first_vertex((208, 208), hit)
    assert not probe.near_first_vertex(hit, None)

    context = SimpleNamespace(
        mode="OBJECT", region_data=object(),
        area=SimpleNamespace(regions=[], tag_redraw=lambda: None),
        region=SimpleNamespace(x=0, y=0, width=500, height=500),
    )
    operator = SimpleNamespace(
        session=session, placement=None, close_pressed=False, target=(),
        context_key=lambda _: (), screen_position=lambda *_: hit,
        cleanup=session.cancel, report=lambda *_: None,
    )
    operator.over_first_vertex = lambda ctx, pixel: operator_class.over_first_vertex(operator, ctx, pixel)
    operator.finish = lambda _, **args: operator_class.finish(operator, bpy.context, **args)

    def send(event_type, value="PRESS", *, pixel=hit, ctrl=False, alt=False):
        event = SimpleNamespace(
            type=event_type, value=value, mouse_x=pixel[0], mouse_y=pixel[1],
            ctrl=ctrl, alt=alt, shift=False, oskey=False,
        )
        return operator_class.modal(operator, context, event)

    probe._active = operator
    assert bpy.ops.wm.tool_set_by_id(name=probe.SplineMakerDrawTool.bl_idname, space_type="VIEW_3D") == {"FINISHED"}
    try:
        assert send("LEFTMOUSE") == {"RUNNING_MODAL"}
        assert send("LEFTMOUSE", "RELEASE") == {"RUNNING_MODAL"}
        assert len(session.points) == 2 and set(bpy.data.objects) == before
        session.place(last)
        assert send("BACK_SPACE") == {"RUNNING_MODAL"}
        assert len(session.points) == 2
        session.place(last)
        assert send("Z", ctrl=True) == {"RUNNING_MODAL"}
        assert len(session.points) == 2
        session.place(last)
        assert send("RIGHTMOUSE", alt=True) == {"PASS_THROUGH"}
        assert send("LEFTMOUSE") == {"RUNNING_MODAL"}
        assert send("LEFTMOUSE", "RELEASE", pixel=(240, 200)) == {"RUNNING_MODAL"}
        assert set(bpy.data.objects) == before
        assert send("LEFTMOUSE", pixel=(206, 208)) == {"RUNNING_MODAL"}
        assert send("LEFTMOUSE", "RELEASE") == {"FINISHED"}
    finally:
        probe._active = None

    obj = bpy.context.view_layer.objects.active
    assert not session.points and set(bpy.data.objects) - before == {obj}
    assert bpy.context.workspace.tools.from_space_view3d_mode("OBJECT").idname == "builtin.select_box"
    bpy.context.view_layer.update()
    spline = obj.data.splines[0]
    assert spline.use_cyclic_u and len(spline.bezier_points) == 3
    start, _, end = spline.bezier_points
    assert start.handle_left_type == "ALIGNED"
    assert (obj.matrix_world @ start.handle_left - plane.to_world(first - tangent)).length < 1e-5
    assert end.handle_right_type == "VECTOR"
    expected = plane.to_world(last + (first - last) / 3)
    assert (obj.matrix_world @ end.handle_right - expected).length < 1e-5


def assert_view_projection(probe):
    region = SimpleNamespace(width=1280, height=720)
    front = Quaternion((1, 0, 0), radians(90))
    side = Quaternion((0, 0, 1), radians(90)) @ front
    angled = Quaternion((1, 1, 0), radians(33))
    cursor = Vector((4, -2, 3))
    local = Vector((1.25, -0.75, 0))
    for start in (Quaternion(), front, side, angled):
        plane = probe.DrawingPlane(cursor, start)
        session = probe.DrawingSession(plane)
        session.place(Vector((0, 0, 0)))
        snapped = session.placement_anchor(local, snap=True)
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
                assert (session.placement_anchor(actual, snap=True) - snapped).length < 1e-4


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
        bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
        try:
            bpy.ops.curve.select_all(action="DESELECT")
            point, neighbor = obj.data.splines[0].bezier_points
            anchor = point.co.copy()
            left, right = point.handle_left.copy(), point.handle_right.copy()
            neighbor_right = neighbor.handle_right.copy()
            point.select_control_point = True
            assert bpy.ops.wm.tool_set_by_id(name="builtin.select_box") == {"FINISHED"}
            assert not bpy.ops.spline_maker.tool_shortcut.poll()
            for mode in ("SELECT", "MOVE", "ROTATE", "SCALE"):
                if mode in {"ROTATE", "SCALE"}:
                    assert bpy.ops.spline_maker.switch_tangent_tool(target=mode) == {"FINISHED"}
                else:
                    assert bpy.ops.wm.tool_set_by_id(name=probe.tool_id(mode)) == {"FINISHED"}
                assert probe.active_mode(bpy.context) == mode
                assert point.select_control_point
                assert bpy.ops.spline_maker.tangent_step.poll() == (
                    mode in {"ROTATE", "SCALE"}
                )
                assert (probe.active_mode(bpy.context) == "MOVE" and probe.move_origin(bpy.context) is not None) == (mode == "MOVE")
                if mode == "ROTATE":
                    assert bpy.ops.spline_maker.tangent_step() == {"FINISHED"}
                    rotation = Matrix.Rotation(radians(15), 3, "Z")
                    assert (point.handle_left - (anchor + rotation @ (left - anchor))).length < 1e-5
                    assert (point.handle_right - (anchor + rotation @ (right - anchor))).length < 1e-5
            rotated_left, rotated_right = point.handle_left.copy(), point.handle_right.copy()
            point.select_control_point = False
            point.select_left_handle = True
            assert not bpy.ops.spline_maker.tangent_step.poll()
            point.select_control_point = True
            assert bpy.ops.spline_maker.tangent_step() == {"FINISHED"}
            expected_left = anchor + (rotated_left - anchor) * 1.25
            assert (point.handle_left - expected_left).length < 1e-5
            assert (point.handle_right - (anchor + (rotated_right - anchor) * 1.25)).length < 1e-5
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
