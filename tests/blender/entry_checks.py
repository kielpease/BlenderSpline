"""Mode-entry regression through merged keymaps, without claiming UI dispatch."""

from pathlib import Path
from types import SimpleNamespace

import bpy

from control_checks import Layout


def run(module):
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    configs = bpy.context.window_manager.keyconfigs
    previous = configs.active.name
    industry = next(Path(path) / "Industry_Compatible.py" for path in bpy.utils.preset_paths("keyconfig")
                    if (Path(path) / "Industry_Compatible.py").exists())

    def matching(key):
        configs.update()
        names = ("Object Non-modal", "Curve" if bpy.context.mode == "EDIT_CURVE" else "Object Mode", "3D View")
        return [item for name in names for item in configs.user.keymaps[name].keymap_items
                if item.active and item.type == key and item.value == "PRESS"
                and not (item.shift or item.ctrl or item.alt or item.oskey)]

    def dispatch(key):
        for item in matching(key):
            category, name = item.idname.split(".")
            op = getattr(getattr(bpy.ops, category), name)
            if not op.poll():
                continue
            assert category == "spline_maker", (configs.active.name, key, item.idname)
            kwargs = {prop.identifier: getattr(item.properties, prop.identifier)
                      for prop in item.properties.bl_rna.properties
                      if prop.identifier != "rna_type" and item.properties.is_property_set(prop.identifier)}
            assert op(**kwargs) == {"FINISHED"}
            return
        raise AssertionError((configs.active.name, key, "No applicable binding"))

    def assert_select():
        assert module.feasibility.active_mode(bpy.context) == "SELECT"
        layout = Layout()
        module.feasibility.VIEW3D_PT_spline_maker_probe.draw(SimpleNamespace(layout=layout), bpy.context)
        buttons = [op for name, op in layout.operators
                   if name == "spline_maker.switch_tangent_tool" and op.target == "SELECT"]
        assert len(buttons) == 1 and buttons[0].ui_kwargs["depress"] is True

    try:
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.spline_maker.add_test_curve()
            obj = bpy.context.object
            before = [module.edit_drag.snapshot(p) for p in obj.data.splines[0].bezier_points]
            for use_industry in (False, True):
                if use_industry:
                    assert bpy.utils.keyconfig_set(str(industry))
                for key in ("ONE", "SIX"):
                    for exit_path in ("custom", "native"):
                        # Re-entry from the old native Select Box state must
                        # activate Q before any selection/sidebar click.
                        dispatch(key)
                        assert bpy.context.mode == "EDIT_CURVE" and bpy.context.edit_object == obj
                        assert module.segment_selection.level(bpy.context) == "VERTEX"
                        assert_select()
                        for mode in ("MOVE", "ROTATE", "SCALE"):
                            bpy.ops.spline_maker.switch_tangent_tool(target=mode)
                            dispatch("Q")
                            assert_select()
                        bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
                        assert not bpy.ops.spline_maker.tool_shortcut.poll()  # Native W/E/R remain native.
                        dispatch("Q")
                        assert_select()
                        bpy.ops.spline_maker.selection_level(target="WHOLE")
                        selection = [(p.select_control_point, p.select_left_handle, p.select_right_handle)
                                     for p in obj.data.splines[0].bezier_points]
                        bpy.ops.wm.tool_set_by_id(name="builtin.move")
                        dispatch("Q")
                        assert_select()
                        assert module.segment_selection.level(bpy.context) == "WHOLE"
                        assert [(p.select_control_point, p.select_left_handle, p.select_right_handle)
                                for p in obj.data.splines[0].bezier_points] == selection
                        if exit_path == "custom":
                            bpy.ops.spline_maker.finish_edit()
                        else:
                            bpy.ops.object.mode_set(mode="OBJECT")
                            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
                        assert bpy.context.object == obj and obj.select_get()
                        assert [module.edit_drag.snapshot(p) for p in obj.data.splines[0].bezier_points] == before
                # Native entry (mode dropdown/other binding), followed by 1/6,
                # must also select Q immediately.
                for key in ("ONE", "SIX"):
                    bpy.ops.object.mode_set(mode="EDIT")
                    bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
                    dispatch(key)
                    assert_select()
                    bpy.ops.spline_maker.finish_edit()
            bpy.ops.object.select_all(action="DESELECT")
            assert not bpy.ops.spline_maker.enter_vertex_edit.poll()
            assert not bpy.ops.spline_maker.enter_edit.poll()
            bpy.ops.mesh.primitive_cube_add()
            for mode in ("OBJECT", "EDIT"):
                bpy.ops.object.mode_set(mode=mode)
                assert not bpy.ops.spline_maker.enter_vertex_edit.poll()
                assert not bpy.ops.spline_maker.enter_edit.poll()
                assert not bpy.ops.spline_maker.select_shortcut.poll()
            bpy.ops.object.mode_set(mode="OBJECT")
            print("1/6 re-entry, Q activation/button state, merged keymap priority and native guards passed")
    finally:
        configs.active = configs[previous]
