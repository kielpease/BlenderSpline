"""Install a local package and check the enable, disable, re-enable cycle."""

import importlib
import os
from pathlib import Path
import sys

import bpy


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
    ui = importlib.import_module(f"{module_name}.ui")

    assert_enabled(module_name, menu, ui)
    assert bpy.ops.preferences.addon_disable(module=module_name) == {"FINISHED"}
    assert_disabled(module_name, menu, ui)
    assert bpy.ops.preferences.addon_enable(module=module_name) == {"FINISHED"}
    assert_enabled(module_name, menu, ui)
    assert bpy.ops.preferences.addon_disable(module=module_name) == {"FINISHED"}
    assert_disabled(module_name, menu, ui)
    print(f"Spline Maker registration smoke test passed on {bpy.app.version_string}")


def assert_enabled(module_name, menu, ui):
    assert module_name in bpy.context.preferences.addons
    assert all(cls.is_registered for cls in ui.CLASSES)
    assert menu.draw._draw_funcs.count(ui.draw_curve_add_menu) == 1

    area = next(area for area in bpy.context.window.screen.areas if area.type == "VIEW_3D")
    with bpy.context.temp_override(area=area):
        before = set(bpy.data.objects)
        assert bpy.ops.spline_maker.draw_spline() == {"CANCELLED"}
        assert set(bpy.data.objects) == before


def assert_disabled(module_name, menu, ui):
    assert module_name not in bpy.context.preferences.addons
    assert not any(cls.is_registered for cls in ui.CLASSES)
    assert ui.draw_curve_add_menu not in menu.draw._draw_funcs


if __name__ == "__main__":
    main(Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True))
