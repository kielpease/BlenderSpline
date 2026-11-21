"""Run SM-017 in an isolated Blender window with --enable-event-simulate."""

import importlib
import os
from pathlib import Path
import sys
import traceback

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).parent))
from lifecycle_checks import activate, add_curve, geometry, viewport


def send(point, kind="MOUSEMOVE", value="PRESS", **modifiers):
    context = bpy.context
    x = round(context.region.x + point[0])
    y = round(context.region.y + point[1])
    if kind == "MOUSEMOVE":
        context.window.cursor_warp(x, y)
        value = "NOTHING"
    context.window.event_simulate(type=kind, value=value, x=x, y=y, **modifiers)


def move_drag(module, context):
    gizmos = module.transform_gizmos
    group = gizmos._groups[gizmos.viewport_key(context)]
    gizmo = next(gizmo for gizmo, mode, _, facing in group.controls if mode == "MOVE" and facing)
    start = location_3d_to_region_2d(context.region, context.region_data, gizmo.matrix_world.translation)
    send(start)
    yield "hover move"
    assert gizmo.is_highlight
    send(start, "LEFTMOUSE")
    yield "start Move"
    assert module.edit_drag._active is not None
    end = start + Vector((35, 26))
    send(end)
    yield "preview Move"
    return end


def drawing(module):
    assert bpy.ops.wm.tool_set_by_id(name=module.drawing_probe.SplineMakerDrawTool.bl_idname) == {"FINISHED"}
    start = Vector((220, 180))
    send(start)
    yield "hover Draw Spline"
    send(start, "LEFTMOUSE")
    yield "start Draw Spline"
    send(start, "LEFTMOUSE", value="RELEASE")
    yield "first preview vertex"
    assert module.drawing_probe._active is not None
    assert len(module.drawing_probe._active.session.points) == 1


def check(archive, test_directory):
    context = bpy.context
    context.preferences.filepaths.temporary_directory = str(test_directory)
    repo = next(repo for repo in context.preferences.extensions.repos if repo.module == "user_default")
    assert Path(repo.directory).resolve().is_relative_to(test_directory)
    assert bpy.ops.extensions.package_install_files(
        filepath=str(archive), repo=repo.module, enable_on_install=True
    ) == {"FINISHED"}
    name = f"bl_ext.{repo.module}.spline_maker"
    module = importlib.import_module(name)
    preset = Path(bpy.utils.preset_paths("keyconfig")[0]) / "Industry_Compatible.py"
    bpy.ops.preferences.keyconfig_activate(filepath=str(preset))
    context.region_data.view_rotation = Quaternion()
    context.region_data.view_perspective = "ORTHO"
    context.region_data.view_distance = 13
    send((180, 170), "ESC")
    yield "dismiss startup"

    scene = context.scene
    first = add_curve(scene, "Lifecycle first", closed=True)
    second = add_curve(scene, "Lifecycle second")
    second.location.x = 4
    other_scene = bpy.data.scenes.new("Lifecycle second scene")
    other = add_curve(other_scene, "Lifecycle other scene")
    state = geometry(first)
    second_state, other_state = geometry(second), geometry(other)

    yield from drawing(module)
    session = module.drawing_probe._active.session
    assert bpy.ops.wm.tool_set_by_id(name="builtin.select_box") == {"FINISHED"}
    yield "leave Draw Spline for native Select Box"
    assert module.drawing_probe._active is None and not session.points
    assert geometry(first) == state and geometry(second) == second_state
    print("Lifecycle viewport: switching from Draw Spline cleared the live overlay and placement.")

    def enter_move(obj):
        activate(obj)
        assert bpy.ops.spline_maker.enter_edit() == {"FINISHED"}
        assert bpy.ops.spline_maker.selection_level(target="WHOLE") == {"FINISHED"}
        assert bpy.ops.spline_maker.switch_tangent_tool(target="MOVE") == {"FINISHED"}

    enter_move(first)
    yield "first curve Move tool"
    yield from move_drag(module, context)
    assert geometry(first) != state and geometry(second) == second_state
    assert bpy.ops.wm.tool_set_by_id(name="builtin.select_box") == {"FINISHED"}
    yield "native tool switch during a drag"
    assert module.edit_drag._active is None and geometry(first) == state
    send((300, 250), "LEFTMOUSE", value="RELEASE")
    yield "old button release after tool switch"

    assert bpy.ops.spline_maker.switch_tangent_tool(target="MOVE") == {"FINISHED"}
    yield "Move again before scene change"
    yield from move_drag(module, context)
    assert geometry(first) != state
    context.window.scene = other_scene
    yield "scene change during a drag"
    assert context.scene == other_scene and module.edit_drag._active is None
    assert geometry(first) == state and geometry(other) == other_state
    send((300, 250), "LEFTMOUSE", value="RELEASE")
    yield "old button release in second scene"
    print("Lifecycle viewport: a tool or scene switch rolled back Move on its original curve.")

    context.window.scene = scene
    yield "return to original scene"
    if context.mode == "EDIT_CURVE":
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    enter_move(first)
    yield "Move before save"
    yield from move_drag(module, context)
    assert geometry(first) != state
    path = test_directory / "viewport-lifecycle.blend"
    assert bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=False) == {"FINISHED"}
    yield "save during a drag"
    assert module.edit_drag._active is None and geometry(first) == state
    send((300, 250), "LEFTMOUSE", value="RELEASE")
    yield "old button release after save"
    if context.mode == "EDIT_CURVE":
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    yield from drawing(module)
    assert bpy.ops.wm.open_mainfile(filepath=str(path)) == {"FINISHED"}
    yield "open project during drawing"
    assert not any(module.lifecycle.active_gestures())
    assert not bpy.app.timers.is_registered(module.lifecycle.check_gestures)
    first = bpy.data.objects["Lifecycle first"]
    assert geometry(first) == state
    assert geometry(bpy.data.objects["Lifecycle second"]) == second_state
    assert geometry(bpy.data.objects["Lifecycle other scene"]) == other_state
    assert context.window_manager.spline_maker_selection_level == "VERTEX"
    assert module.lifecycle.tool_id(context) == "builtin.select_box"
    print("Lifecycle viewport: saving canceled an edit preview and reopening discarded a drawing preview.")

    if context.mode == "EDIT_CURVE":
        assert bpy.ops.spline_maker.finish_edit() == {"FINISHED"}
    enter_move(first)
    yield "Move before native undo"
    end = yield from move_drag(module, context)
    committed = geometry(first)
    assert committed != state
    send(end, "LEFTMOUSE", value="RELEASE")
    yield "commit Move"
    assert module.edit_drag._active is None and geometry(first) == committed
    yield from move_drag(module, context)
    assert geometry(first) != committed
    assert bpy.ops.ed.undo() == {"FINISHED"}
    yield "undo during Move"
    assert module.edit_drag._active is None
    assert geometry(bpy.data.objects["Lifecycle first"]) == state
    assert bpy.ops.ed.redo() == {"FINISHED"}
    yield "redo committed Move"
    first = bpy.data.objects["Lifecycle first"]
    assert geometry(first) == committed
    send((300, 250), "LEFTMOUSE", value="RELEASE")
    yield "old button release after undo"

    assert bpy.ops.spline_maker.switch_tangent_tool(target="MOVE") == {"FINISHED"}
    yield "Move before disabling"
    yield from move_drag(module, context)
    assert geometry(first) != committed
    assert bpy.ops.preferences.addon_disable(module=name) == {"FINISHED"}
    yield "disable while Move is live"
    assert geometry(first) == committed
    assert not any(module.lifecycle.active_gestures())
    assert not module.transform_gizmos._groups
    assert all(callback not in handlers for handlers, callback in module.lifecycle._HANDLERS)
    assert not bpy.app.timers.is_registered(module.lifecycle.check_gestures)
    assert module.vertex_selection._handler is None and module.vertex_selection._cursor_handler is None
    assert module.display._handler is None
    assert module.lifecycle.tool_id(context) == "builtin.select_box"
    send((300, 250), "LEFTMOUSE", value="RELEASE")
    yield "old button release after disabling"
    assert bpy.ops.preferences.addon_enable(module=name) == {"FINISHED"}
    yield "re-enable in the same viewport"
    assert all(handlers.count(callback) == 1 for handlers, callback in module.lifecycle._HANDLERS)
    assert module.display._handler is not None and module.vertex_selection._handler is not None
    send((300, 250), "Q")
    yield "Q after re-enable"
    assert module.feasibility.active_mode(context) == "SELECT"
    assert geometry(first) == committed
    print("Lifecycle viewport: native Undo/Redo and disable/re-enable left no stale preview or duplicate handler.")

    send((300, 250), "ESC")
    yield "exit Edit Mode after re-enable"
    assert context.mode == "OBJECT"
    objects = {obj.name for obj in context.scene.objects}
    yield from drawing(module)
    point = (320, 250)
    send(point, "LEFTMOUSE")
    send(point, "LEFTMOUSE", value="RELEASE")
    yield "second drawing point"
    send(point, "RIGHTMOUSE")
    yield "commit new curve"
    created = context.object.name
    assert {obj.name for obj in context.scene.objects} == objects | {created}
    assert module.drawing_probe._active is None
    drawing_state = geometry(context.object)
    assert bpy.ops.ed.undo() == {"FINISHED"}
    yield "undo curve creation"
    assert {obj.name for obj in context.scene.objects} == objects
    assert not any(module.lifecycle.active_gestures())
    assert bpy.ops.ed.redo() == {"FINISHED"}
    yield "redo curve creation"
    assert geometry(bpy.data.objects[created]) == drawing_state
    activate(bpy.data.objects[created])
    assert bpy.ops.object.delete("EXEC_DEFAULT", True) == {"FINISHED"}
    yield "delete active spline"
    assert {obj.name for obj in context.scene.objects} == objects
    assert bpy.ops.ed.undo() == {"FINISHED"}
    yield "undo deletion"
    assert geometry(bpy.data.objects[created]) == drawing_state
    assert geometry(bpy.data.objects["Lifecycle first"]) == committed
    print("Lifecycle viewport: undo through curve creation and deletion preserved neighboring curves.")


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    archive, test_directory = Path(args[0]).resolve(), Path(os.environ["BLENDER_USER_RESOURCES"]).resolve()
    result = test_directory / "lifecycle-viewport.txt"
    steps = check(archive, test_directory)
    phase = "startup"

    def tick():
        nonlocal phase
        try:
            with viewport():
                phase = next(steps)
            return 0.3
        except StopIteration:
            result.write_text(f"SM-017 viewport tests passed on Blender {bpy.app.version_string}", encoding="utf-8")
        except Exception:
            result.write_text(f"{phase}\n{traceback.format_exc()}", encoding="utf-8")
        bpy.ops.wm.quit_blender()
        return None

    bpy.app.timers.register(tick, first_interval=1.5, persistent=True)


if __name__ == "__main__":
    main()
