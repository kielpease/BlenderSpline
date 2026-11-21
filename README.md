# Splines for Blender

Splines is a Blender extension for drawing and editing native Bézier curves in the 3D Viewport. Draw mixed straight and curved outlines directly, then work at the vertex, segment, spline, or whole-curve level.

**Local build 0.18.0** · Verified on Blender 5.2.4 LTS for Windows, with Default and Industry Compatible keymap coverage.

## Quick start

1. Build `spline_maker-0.18.0.zip` from this checkout. In Blender, go to **Edit → Preferences → Get Extensions** and choose **Install from Disk** from the top-right menu. [Build instructions](docs/BUILD.md#build-and-validate)
2. In Object Mode, choose **Add → Curve → Draw Spline** or open the **Splines** tab in the viewport sidebar with **N**. Click to place corners or drag to pull linked handles. Right-click to finish an open spline. Click the first point to close it after placing at least three vertices.
3. Select one Bézier curve and press **6** to edit. Use **1–4** for the selection level and **Q/W/E/R** for Select, Move, Rotate, or Scale. Press **Enter** to finish editing.

## Features

- View-aligned drawing at the 3D cursor's depth, with first-point grid snapping, 45° direction constraints, and click-drag Bézier closure.
- Direct handle editing, a right-click vertex-type menu, and separate selection levels for vertices, segments, splines, and all geometry.
- Move, Rotate, and Scale gizmos with world-axis constraints, Shift snapping, and editable world coordinates in the sidebar.
- Native Undo/Redo for completed gestures and native Bézier geometry that remains editable after saving and reopening the project.

## Compatibility and scope

Splines editing operates on one editable all-Bézier curve object at a time. That object can contain multiple splines. The custom gizmos edit the source geometry in Curve Edit Mode. Use Blender Object Mode to transform the object and its origin.

The current package is for local testing. Public extension distribution awaits a license decision. Insert/delete, attach/detach, welding, and profile geometry are planned features.

- [User guide](docs/USER_GUIDE.md) for controls, working examples, and known limits
- [Build and test instructions](docs/BUILD.md) for packaging and verification
- [Test results](docs/TEST_PLAN.md#sm-018-package-and-user-guide)
- [Roadmap](docs/ROADMAP.md) for the upcoming editing features
