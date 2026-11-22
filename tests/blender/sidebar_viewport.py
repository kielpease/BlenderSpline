"""Check sidebar tab switching in an isolated window with --enable-event-simulate."""

import os
from pathlib import Path
import sys
import traceback

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).parent))
from lifecycle_checks import viewport
from lifecycle_viewport import send
from profile_checks import line


def click(point):
    send(point, "LEFTMOUSE")
    send(point, "LEFTMOUSE", "RELEASE")


def project(obj, point):
    context = bpy.context
    return location_3d_to_region_2d(context.region, context.region_data, obj.matrix_world @ Vector(point))


def expect_tab(sidebar, category):
    # The sidebar layout can redraw a frame after selection and timer callbacks.
    for _ in range(5):
        if sidebar.active_panel_category == category:
            return
        yield f"wait for the {category} sidebar tab"
    assert sidebar.active_panel_category == category, sidebar.active_panel_category


def check(archive, test_directory, industry):
    context = bpy.context
    context.preferences.filepaths.temporary_directory = str(test_directory)
    repo = next(repo for repo in context.preferences.extensions.repos if repo.module == "user_default")
    assert Path(repo.directory).resolve().is_relative_to(test_directory)
    assert bpy.ops.extensions.package_install_files(
        filepath=str(archive), repo=repo.module, enable_on_install=True
    ) == {"FINISHED"}
    if industry:
        preset = Path(bpy.utils.preset_paths("keyconfig")[0]) / "Industry_Compatible.py"
        assert bpy.ops.preferences.keyconfig_activate(filepath=str(preset)) == {"FINISHED"}
    context.region_data.view_rotation = Quaternion()
    context.region_data.view_perspective = "ORTHO"
    context.region_data.view_distance = 15
    context.space_data.show_region_ui = True
    send((190, 170), "ESC")
    yield "dismiss startup"

    for obj in context.scene.objects:
        obj.hide_set(True)
    curve = line("Sidebar spline")
    curve.location.x = -5
    assert bpy.ops.mesh.primitive_cube_add(size=1.6, location=(3, 0, 0)) == {"FINISHED"}
    box = context.active_object
    context.view_layer.update()
    sidebar = next(region for region in context.area.regions if region.type == "UI")
    sidebar.active_panel_category = "Item"
    yield "show the Item tab for the box"
    assert sidebar.active_panel_category == "Item"

    curve_point = project(curve, (1, 0, 0))
    box_point = project(box, (0, 0, 0))
    send(curve_point)
    yield "hover the spline"
    click(curve_point)
    yield "select the spline"
    assert context.active_object == curve
    yield from expect_tab(sidebar, "Spline")

    send(box_point)
    yield "hover the existing box"
    click(box_point)
    yield "select the existing box"
    assert context.active_object == box
    yield from expect_tab(sidebar, "Item")
    sidebar.active_panel_category = "View"
    context.area.tag_redraw()
    yield "choose a native tab"
    assert sidebar.active_panel_category == "View"

    send(curve_point)
    yield "return to the spline"
    click(curve_point)
    yield "select the spline again"
    assert context.active_object == curve
    yield from expect_tab(sidebar, "Spline")

    send(curve_point, "SIX")
    yield "edit the selected spline"
    assert context.mode == "EDIT_CURVE"
    yield from expect_tab(sidebar, "Spline")
    send(curve_point, "RET")
    yield "finish spline editing"
    assert context.mode == "OBJECT"
    yield from expect_tab(sidebar, "Spline")

    context.scene.cursor.location = (0, -3, 0)
    send(curve_point, "TAB" if industry else "F3")
    yield "open native operator search"
    for character in "add cube":
        key = "SPACE" if character == " " else character.upper()
        send(curve_point, key, unicode=character)
        send(curve_point, key, "RELEASE")
    yield "search Add Cube"
    send(curve_point, "RET")
    yield "create a box with native Add Cube"
    assert context.active_object.type == "MESH" and context.active_object != box
    yield from expect_tab(sidebar, "Item")
    created_name = context.active_object.name

    send(curve_point, "Z", ctrl=True)
    yield "undo creation and restore the spline"
    assert context.active_object.name == "Sidebar spline"
    assert created_name not in context.scene.objects
    yield from expect_tab(sidebar, "Spline")
    assert bpy.ops.ed.redo() == {"FINISHED"}
    yield "redo creation"
    assert context.active_object.name == created_name
    yield from expect_tab(sidebar, "Item")

    context.space_data.show_region_ui = False
    send(curve_point)
    yield "hover the spline with the sidebar closed"
    click(curve_point)
    yield "select the spline with the sidebar closed"
    assert context.active_object.name == "Sidebar spline"
    assert not context.space_data.show_region_ui
    send(curve_point, "RIGHT_BRACKET" if industry else "N", ctrl=industry)
    yield "reopen the sidebar with the current keymap"
    assert context.space_data.show_region_ui
    yield from expect_tab(sidebar, "Spline")


def main():
    archive, preset = sys.argv[sys.argv.index("--") + 1:]
    test_directory = Path(os.environ["BLENDER_USER_RESOURCES"]).resolve()
    result = test_directory / "sidebar-viewport.txt"
    steps = check(Path(archive).resolve(), test_directory, preset == "industry")
    phase = "startup"

    def tick():
        nonlocal phase
        try:
            with viewport():
                phase = next(steps)
            return 0.35
        except StopIteration:
            result.write_text(f"PASS on Blender {bpy.app.version_string} ({preset})", encoding="utf-8")
        except Exception:
            result.write_text(f"{phase}\n{traceback.format_exc()}", encoding="utf-8")
        bpy.ops.wm.quit_blender()
        return None

    bpy.app.timers.register(tick, first_interval=1.5)


if __name__ == "__main__":
    main()
