# Project instructions

## Product and scope

Build Spline Maker, a Blender extension for direct drawing and editing of native Bezier curves. Read `docs/INTERACTION_SPEC.md`, `docs/ROADMAP.md`, and the current issue before editing. Primary target is Blender 5.2.4 LTS on Windows. Implemented drawing, selection and transform behavior is recorded below; distinguish owner acceptance, background checks and unverified UI cases.

Implement the requested issue only, plus necessary dependencies. Do not implement future wall rendering, attaching, welding, or topology editing early. Preserve native editable Bézier curves where practical. Do not silently convert source curves to meshes.

## Interaction rules

- Click corners; click-drag Bézier handles; Shift constrains placement in 45-degree increments on a fixed drawing plane.
- Q/W/E/R select tools. The 0.15.3 candidate puts 1 Vertex, 2 Segment, 3 Spline, and 4 All at the top of the Edit panel. Enter finishes editing, and Esc still cancels a drag or exits when idle. 3 auto-selects the sole spline, or selects individual open or closed paths when multiple paths exist. 6 enters Spline Maker vertex editing for a single selected editable Bezier curve. Preserve native 5 and other-object mode controls. Keep extension bindings scoped.
- All essential actions need visible buttons or contextual menu entries.
- For one selected editable Bezier curve, 1/6 from Object Mode enter Vertex editing with Spline Maker Q Select active. In supported Curve Edit Mode, Q can enter Spline Maker Select from a native tool while preserving component level/selection. W/E/R remain scoped to an active Spline Maker tool.
- Segment box selection selects a segment when any part of its projected curve touches or crosses the box, in either drag direction. Spline/Whole box selection still requires complete enclosure.
- Vertex Move centers its gizmo on the selected anchors. Vertex Rotate/Scale defaults to editing tangents about each selected anchor. E Rotate also offers Group, which rotates selected anchors and handles together. Segment/Spline/Whole Rotate/Scale transforms source geometry about the average of unique selected anchors. Shared endpoints transform once. Direct handle diamonds remain freely draggable.
- Do not substitute a hotkey-heavy workflow for the specification.
- Distinguish breaking tangent linkage (Bézier Corner) from splitting spline topology (Break).
- Closed-region selection is a logical spline region, not editable generated mesh faces.
- Menu entry is required; investigate the toolbar Add flyout separately rather than claiming both use the same API.
- Unregister must clean up classes, menus, tools, keymaps, handlers, and draw callbacks owned by the extension.

## Engineering

Use Python and Blender's supported extension APIs. Verify version-specific APIs against official documentation and the installed Blender. Keep math/state logic separate from viewport/UI code. Prefer small modules with clear ownership. No network, external binaries, or third-party runtime dependencies for the first release.

Design reliable undo boundaries; do not assume Blender automatically records each click inside a long-running modal operator. Support cancel rollback and guard against stale data references after undo. Keep viewport navigation available. Persist only document settings that belong in the .blend file; clear temporary session state on tool exit.

## Validation and reporting

Run focused math tests and Blender background smoke tests when relevant. Mouse interaction, gizmos, picking, and navigation require real Blender UI testing. Never equate syntax checks or mocks with UI verification. Report exact Blender version, checks run, and anything untested.

For each change: summarize behavior, files changed, tests, limitations, and a short user test procedure. Update relevant docs and changelog when present. Do not increase scope or make unsupported compatibility claims to satisfy a milestone.

## Session handoff: 2026-11-21

- The stable installer contains **0.18.0**, packaged from the owner-accepted **0.17.0** editing and lifecycle build.
- Repository: `https://github.com/kielpease/BlenderSpline`, branch `main`. Inspect local changes before pulling on another machine.
- **SM-016 interaction integration** was pushed to `main` in commit `0413429` with the **0.16.0** ZIP available locally under `dist/`.
- `drag_navigation.py` forwards viewport navigation events and detects projection changes during edit gestures. Move, Rotate, Scale, and direct handles rebase their input from the applied preview. Edit entry via **1** or **6** records a native Edit Mode checkpoint for the first transform Undo.
- **SM-017 lifecycle and save/reopen** passed on Blender 5.2.4 LTS for Windows. [Test results](docs/TEST_PLAN.md#sm-017-lifecycle-and-savereopen)
- **SM-018 packaging and user guide** completes the local build. The next editing task is **Insert Vertex** with Bézier shape preservation. [User guide](docs/USER_GUIDE.md) · [Roadmap](docs/ROADMAP.md#m6--extended-editing)

### Current implementation details

- `feasibility.py`: workspace tools, keymaps, entry/exit, Edit sidebar and shared selection-center pivots. `1/6` from Object Mode enter one selected editable Bezier curve with Q Select active; Q can also enter from a supported native Curve Edit tool. Native W/E/R stay native until Spline Maker is active.
- `segment_selection.py`: native segment identity, curve sampling, crossing-box selection and level controls. `region_selection.py`'s internal `REGION` value now means the visible **3 Spline** level; it handles open and closed paths. Keep that distinction when reading earlier Region-only planning.
- `edit_drag.py`: Move and shared world-space ray/plane projection. `tangent_drag.py`: Vertex tangent editing and Segment/Spline/Whole geometry rotation/scaling. Shared endpoints transform once. Composite pivot is the average of unique selected anchors; Whole includes hidden points.
- `transform_gizmos.py`: one tool-owned gizmo group. Q hides controls. Move hides its gizmo during a drag, and Rotate and Scale retain their controls and readout. The offset blue XY square scales X/Y together with world Z fixed in composite R mode. The white center scales XYZ uniformly.
- `lifecycle.py` guards live gestures against viewport, scene, object, and tool changes. Native file and history callbacks cancel previews before Blender replaces or writes data. Disable removes owned callbacks and returns open viewports using Splines tools to native Select Box.
- Geometry transforms remain in Curve Edit Mode with the object matrix/origin fixed. Direct object-location changes in Curve Edit Mode did not participate in native curve Undo in the installed-version probe. Use Object Mode for object transforms. Geometry transforms preserve vertex types and native Auto/Vector tangent rules.
- Drawing Finish returns to native Select Box. `display.py` colors supported Edit curves and unselected visible Bezier objects; selected Object Mode outlines remain native. The wings checkbox controls native curve normals.

### Build and resume at home

Keep versioned test ZIPs in `dist/` and one owner-approved installer at `stable/spline_maker-stable.zip`. Both folders are Git-ignored. Rebuild after pulling source on another machine and follow the promotion steps in `docs/BUILD.md`. Source is `extension/spline_maker/`; `spline-maker-starter/` is an old starter copy, not the active implementation.

From the repository root, set `$blender` to the local Blender 5.2.4 executable and run:

```powershell
New-Item -ItemType Directory -Force dist | Out-Null
& $blender --command extension build --source-dir extension/spline_maker --output-dir dist
& $blender --command extension validate dist/spline_maker-0.18.0.zip
```

Use the isolated-profile smoke-test command in `docs/BUILD.md`; it sets/restores `BLENDER_USER_RESOURCES` and installs into a fresh directory under `dist`, protecting the normal Blender profile. The entry point is `tests/blender/smoke_registration.py`, which runs the segment, region/spline, controls, Whole Move, transform and entry regression modules. Disable the previous build and restart Blender before installing a new ZIP for hands-on testing.

The manifest license is still the owner's pending-license placeholder for local testing. Do not publish an extension release until that decision is made.
