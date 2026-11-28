"""Open a disposable Circle profile scene for hands-on sidebar checks.

Launch with a fresh BLENDER_USER_RESOURCES directory and pass the candidate ZIP
after --. The normal Blender profile and any other open project are untouched.
"""

from pathlib import Path
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
from lifecycle_checks import viewport
from profile_checks import line


def setup():
    archive = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    resources = Path(os.environ["BLENDER_USER_RESOURCES"]).resolve()
    repo = next(repo for repo in bpy.context.preferences.extensions.repos if repo.module == "user_default")
    assert Path(repo.directory).resolve().is_relative_to(resources)
    assert bpy.ops.extensions.package_install_files(
        filepath=str(archive), repo=repo.module, enable_on_install=True
    ) == {"FINISHED"}
    import importlib
    module = importlib.import_module(f"bl_ext.{repo.module}.spline_maker")
    with viewport():
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()
        obj = line("Circle Sides and Roll preview")
        bpy.ops.spline_maker.toggle_profile()
        modifier = module.profile.profile_modifier(obj)
        module.profile.profile_input(modifier, "Shape").value = "Circle"
        module.profile.profile_input(modifier, "Radius").value = 0.75
        obj.update_tag()
        space = bpy.context.space_data
        space.show_region_ui = True
        space.region_3d.view_rotation = Vector((5, -7, 5)).to_track_quat("Z", "Y")
        space.region_3d.view_location = (1.5, 0, 0)
        space.region_3d.view_distance = 9
        # Let the normal selection-follow timer switch tabs after the sidebar
        # has drawn; category assignment is read-only before its first layout.
        bpy.context.area.tag_redraw()
    bpy.ops.wm.save_as_mainfile(filepath=str(resources / "spline-1.1.0-preview.blend"))
    bpy.ops.ed.undo_push(message="Circle profile preview")
    print(f"Circle profile preview ready on Blender {bpy.app.version_string}", flush=True)


if __name__ == "__main__":
    bpy.app.timers.register(setup, first_interval=2.0)
