"""SM-013 selection/tool integration on real curve data and synthetic gizmos."""

from types import SimpleNamespace

import bpy
from mathutils import Matrix


def run(module):
    area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
    window_region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=window_region):
        bpy.ops.spline_maker.add_test_curve()
        obj = bpy.context.object
        obj.matrix_world = (Matrix.Translation((4, -3, 2)) @ Matrix.Rotation(0.4, 4, "Z")
                            @ Matrix.Diagonal((2, 0.7, 1.2, 1)))
        bpy.context.view_layer.update()
        assert not bpy.ops.spline_maker.enter_selection_level.poll()
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            # The visible panel exposes all levels even in a native Edit tool.
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
            layout = Layout()
            module.feasibility.VIEW3D_PT_spline_maker_probe.draw(SimpleNamespace(layout=layout), bpy.context)
            assert {op.target for name, op in layout.operators
                    if name == "spline_maker.enter_selection_level"} == {"VERTEX", "SEGMENT", "REGION", "WHOLE"}

            # Each explicit entry action works without a previous Q click.
            for target, _, _ in module.segment_selection.LEVELS:
                bpy.ops.wm.tool_set_by_id(name="builtin.move")
                assert bpy.ops.spline_maker.enter_selection_level.poll()
                assert bpy.ops.spline_maker.enter_selection_level(target=target) == {"FINISHED"}
                assert module.feasibility.active_mode(bpy.context) == "SELECT"
                assert module.segment_selection.level(bpy.context) == target

            controls = [(SimpleNamespace(hide=False), mode, Matrix.Identity(4), False)
                        for mode in ("MOVE", "ROTATE", "SCALE")]
            group = SimpleNamespace(controls=controls)
            full_group = SimpleNamespace(gizmos=Gizmos())
            module.transform_gizmos.VIEW3D_GGT_spline_maker_transform.setup(full_group, bpy.context)
            assert full_group.xy_scale.operator == "spline_maker.tangent_drag"
            assert full_group.xy_scale.props.mode == "SCALE" and full_group.xy_scale.props.axis == "XY"
            assert full_group.xy_scale.matrix_offset.translation.x > 0
            assert full_group.xy_scale.matrix_offset.translation.y > 0
            geometry = [module.edit_drag.snapshot(p) for p in obj.data.splines[0].bezier_points]

            def state():
                return [(p.select_control_point, p.select_left_handle, p.select_right_handle)
                        for s in obj.data.splines for p in s.bezier_points]

            for level, _, _ in module.segment_selection.LEVELS:
                bpy.ops.spline_maker.enter_selection_level(target=level)
                if level == "VERTEX":
                    bpy.ops.curve.select_all(action="DESELECT")
                    obj.data.splines[0].bezier_points[0].select_control_point = True
                elif level == "SEGMENT":
                    module.segment_selection.select(obj.data, {(0, 0)})
                selection = state()
                for _, start, _ in module.feasibility.TOOLS:
                    for _, target, _ in module.feasibility.TOOLS:
                        bpy.ops.spline_maker.switch_tangent_tool(target=start)
                        # Keyboard and visible buttons share the same switch path.
                        assert bpy.ops.spline_maker.tool_shortcut(target=target) == {"FINISHED"}
                        assert bpy.ops.spline_maker.switch_tangent_tool(
                            "EXEC_REGION_WIN", target=target) == {"FINISHED"}
                        assert module.feasibility.active_mode(bpy.context) == target
                        assert module.segment_selection.level(bpy.context) == level
                        assert state() == selection
                        assert [module.edit_drag.snapshot(p) for p in obj.data.splines[0].bezier_points] == geometry
                        module.transform_gizmos.VIEW3D_GGT_spline_maker_transform.draw_prepare(group, bpy.context)
                        module.transform_gizmos.VIEW3D_GGT_spline_maker_transform.draw_prepare(full_group, bpy.context)
                        assert full_group.xy_scale.hide == (target != "SCALE" or level == "VERTEX")
                        visible = {mode for control, mode, _, _ in controls if not control.hide}
                        expected = {target} if target != "SELECT" else set()
                        assert visible == expected, (level, target, visible)
                        for control, _, _, _ in controls:
                            if not control.hide:
                                world_center = obj.matrix_world @ module.feasibility.move_origin(bpy.context)
                                assert (control.matrix_basis.translation - world_center).length < 1e-5
                        if target == "SELECT":
                            assert not bpy.ops.spline_maker.move_drag.poll()
                            assert not bpy.ops.spline_maker.tangent_drag.poll()
                bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
                assert not bpy.ops.spline_maker.tool_shortcut.poll()
                assert bpy.ops.spline_maker.enter_selection_level.poll()
        finally:
            module.transform_gizmos.unregister()
            bpy.context.window_manager.spline_maker_selection_level = "VERTEX"
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.mesh.primitive_cube_add()
        bpy.ops.object.mode_set(mode="EDIT")
        assert not bpy.ops.spline_maker.enter_selection_level.poll()
        bpy.ops.object.mode_set(mode="OBJECT")
        print("SM-013 entry, all-level tool parity, selection preservation and gizmo visibility state passed")


class Gizmos:
    """Capture operator routing and visibility without verifying GPU output."""

    def new(self, kind):
        gizmo = SimpleNamespace(matrix_offset=Matrix.Identity(4))

        def target(name):
            gizmo.operator = name
            gizmo.props = SimpleNamespace()
            return gizmo.props

        gizmo.target_set_operator = target
        return gizmo


class Layout:
    """Capture operator availability without claiming to verify panel rendering."""

    def __init__(self):
        self.operators = []

    def row(self, **kwargs):
        return self

    def operator(self, name, **kwargs):
        op = SimpleNamespace(ui_kwargs=kwargs)
        self.operators.append((name, op))
        return op

    def label(self, **kwargs):
        pass

    def separator(self):
        pass

    def prop(self, *args, **kwargs):
        pass
