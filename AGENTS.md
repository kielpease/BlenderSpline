# Project instructions

## Product and scope

Build Spline, a Blender extension for direct drawing and editing of native Bezier curves. Read `docs/INTERACTION_SPEC.md`, `docs/ROADMAP.md`, and the current issue before editing. Primary target is Blender 5.2.4 LTS on Windows. Record owner acceptance, background checks, and remaining unverified UI cases.

Implement the requested issue only, plus necessary dependencies. Do not implement future wall rendering, attaching, welding, or topology editing early. Preserve native editable Bézier curves where practical. Do not silently convert source curves to meshes.

## Interaction rules

- Click corners; click-drag Bézier handles; Shift constrains placement in 45-degree increments on a fixed drawing plane.
- Q/W/E/R select tools. The Edit panel offers 1 Vertex, 2 Segment, 3 Spline, and an All button. 4 returns to Object Mode from Curve Edit Mode. Enter also finishes editing, and Esc cancels a drag or exits when idle. 3 auto-selects the sole spline, or selects individual open or closed paths when multiple paths exist. 6 enters vertex editing for the active editable Bezier curve. Preserve native 5 and other-object mode controls. Keep extension bindings scoped.
- All essential actions need visible buttons or contextual menu entries.
- For one selected editable Bezier curve in Object Mode, 1 enters Vertex, 2 enters Segment, and 3 enters Spline editing with Q Select active. 6 edits the active Bezier curve by itself when multiple objects are selected. In supported Curve Edit Mode, Q can enter Spline Maker Select from a native tool while preserving component level/selection. W/E/R remain scoped to an active Spline Maker tool.
- Segment box selection selects a segment when any part of its projected curve touches or crosses the box, in either drag direction. Spline/Whole box selection still requires complete enclosure.
- Vertex Move centers its gizmo on the selected anchors. Vertex Rotate defaults to Group in 0.19.0 and offers Tangents for per-anchor rotation. Vertex Scale edits tangents about each selected anchor. Segment/Spline/Whole Rotate/Scale transforms source geometry about the average of unique selected anchors. Shared endpoints transform once. Direct handle diamonds remain freely draggable.
- Do not substitute a hotkey-heavy workflow for the specification.
- Distinguish breaking tangent linkage (Bézier Corner) from splitting spline topology (Break).
- Closed-region selection is a logical spline region, not editable generated mesh faces.
- Menu entry is required; investigate the toolbar Add flyout separately rather than claiming both use the same API.
- Unregister must clean up classes, menus, tools, keymaps, handlers, and draw callbacks owned by the extension.

## Engineering

Use Python and Blender's supported extension APIs. Verify version-specific APIs against official documentation and the installed Blender. Keep math/state logic separate from viewport/UI code. Prefer small modules with clear ownership. No network, external binaries, or third-party runtime dependencies for the first release.

Design reliable undo boundaries; do not assume Blender automatically records each click inside a long-running modal operator. Support cancel rollback and guard against stale data references after undo. Keep viewport navigation available. Persist only document settings that belong in the .blend file; clear temporary session state on tool exit.

## Validation and reporting

- Public updates must follow `docs/RELEASING.md` and update `CHANGELOG.md`. Preserve extension ID `spline_maker` and publish new versions to the existing listing at https://extensions.blender.org/add-ons/spline-maker/. Publishing an owner-accepted stable GitHub release uploads its tested ZIP through the release workflow; ordinary pushes do not. Record upload/publication and Blender update verification separately from build/UI acceptance. Keep API tokens only in GitHub Secrets.

Run focused math tests and Blender background smoke tests when relevant. Mouse interaction, gizmos, picking, and navigation require real Blender UI testing. Never equate syntax checks or mocks with UI verification. Report exact Blender version, checks run, and anything untested.

For each change: summarize behavior, files changed, tests, limitations, and a short user test procedure. Update relevant docs and changelog when present. Do not increase scope or make unsupported compatibility claims to satisfy a milestone.

## Session handoff: 2026-11-21

- The local stable installer contains **0.18.1** and includes the owner-accepted **0.17.0** editing and lifecycle features.
- Repository: `https://github.com/kielpease/BlenderSpline`, branch `main`. Inspect local changes before pulling on another machine.
- **SM-016 interaction integration** was pushed to `main` in commit `0413429` with the **0.16.0** ZIP available locally under `dist/`.
- `drag_navigation.py` forwards viewport navigation events and detects projection changes during edit gestures. Move, Rotate, Scale, and direct handles rebase their input from the applied preview. Edit entry via **1** or **6** records a native Edit Mode checkpoint for the first transform Undo.
- **SM-017 lifecycle and save/reopen** passed on Blender 5.2.4 LTS for Windows. [Test results](docs/TEST_PLAN.md#sm-017-lifecycle-and-savereopen)
- **SM-018 packaging and user guide** completes the local stable build. M6 runs before M5. The owner accepted **0.22.0** and requested a visible **Detach** button in **3 Spline**. Version **0.23.0** adds that button. [Viewport check](docs/BUILD.md#0230-detach) · [Roadmap](docs/ROADMAP.md#m6--extended-editing)
- **M5** starts in the owner-accepted **0.24.0** build with live profiles and direct **2/3** entry from Object Mode. **0.25.0** adds Curve Resolution and remembers the last Rectangle Height and Width in the file. [Viewport check](docs/BUILD.md#0250-curve-resolution-and-profile-defaults)
- **0.25.1** explains when native Edit Mode includes multiple objects and offers **Return to Object Mode**. **0.25.2** makes **Enter** available for this exit while the Splines sidebar tab is visible. [Viewport check](docs/BUILD.md#0252-enter-from-the-splines-panel)
- **0.26.0** adds bounded mitered joins to Rectangle profiles. Use **Update Profile Corners** on a curve with an older generated profile. [Viewport check](docs/BUILD.md#0260-mitered-profile-corners)
- **0.26.1** makes **4** return to Object Mode from any Curve Edit context. **6** edits the active Bézier curve on its own. [Viewport check](docs/BUILD.md#0261-edit-and-object-mode)
- **0.26.2** gives **Enter** and **Numpad Enter** the same exit behavior as **4** in Curve Edit Mode. [Viewport check](docs/BUILD.md#0262-enter-and-numpad-enter)
- **0.26.3** switches the open 3D Viewport sidebar to **Splines** for the active Bézier curve and back to **Item** when selecting or adding a mesh from the Splines tab. [Viewport check](docs/BUILD.md#0263-sidebar-follows-selection)
- **0.26.4** adds the Bézier icon to **Add → Curve → Draw Spline** and documents the current drawing, editing, and profile workflows. [Viewport check](docs/BUILD.md#0264-draw-spline-menu-icon)
- **1.0.0** uses the visible name **Spline**, with **Pease Technology** as maintainer and copyright holder. The extension ID `spline_maker` and operator identifiers preserve the upgrade path. The project and ZIP include the GPLv3 license text.

### Current implementation details

- `feasibility.py`: workspace tools, keymaps, entry/exit, Edit sidebar and shared selection-center pivots. Object Mode entry activates Q Select at the requested level. Native W/E/R stay native until Spline Maker is active.
- `profile.py`: builds and reuses a native Geometry Nodes group. Each object stores its own profile inputs in a modifier. Object Mode Height and Width edits also save the last-entered defaults in the group for newly enabled profiles. Curve Resolution uses the native curve data.
- `segment_selection.py`: native segment identity, curve sampling, crossing-box selection and level controls. `region_selection.py`'s internal `REGION` value now means the visible **3 Spline** level; it handles open and closed paths. Keep that distinction when reading earlier Region-only planning.
- `edit_drag.py`: Move and shared world-space ray/plane projection. `tangent_drag.py`: Vertex tangent editing and Segment/Spline/Whole geometry rotation/scaling. Shared endpoints transform once. Composite pivot is the average of unique selected anchors; Whole includes hidden points.
- `transform_gizmos.py`: one tool-owned gizmo group. Q hides controls. Move hides its gizmo during a drag, and Rotate and Scale retain their controls and readout. The offset blue XY square scales X/Y together with world Z fixed in composite R mode. The white center scales XYZ uniformly.
- `lifecycle.py` guards live gestures against viewport, scene, object, and tool changes. Native file and history callbacks cancel previews before Blender replaces or writes data. Disable removes owned callbacks and returns open viewports using Splines tools to native Select Box.
- Geometry transforms remain in Curve Edit Mode with the object matrix/origin fixed. Direct object-location changes in Curve Edit Mode did not participate in native curve Undo in the installed-version probe. Use Object Mode for object transforms. Geometry transforms preserve vertex types and native Auto/Vector tangent rules.
- Drawing Finish returns to native Select Box. `display.py` colors supported Edit curves and unselected visible Bezier objects; selected Object Mode outlines remain native. The wings checkbox controls native curve normals.

### Build and resume at home

Work-laptop follow-up (2026-11-27): Blender **5.2.5 LTS** is installed. The owner accepted **1.1.0** and authorized publishing it on GitHub and Blender Extensions. It adds Circle Sides (3–1024, default 32), independent Circle Roll (0°), native shaded sidebar boxes, and supported discovery tags. Preserve the tested ZIP when releasing. Current public usage text is maintained in `docs/EXTENSIONS_DESCRIPTION.md`; see `docs/TEST_PLAN.md` for actual checks, distribution status, and remaining UI cases.

Keep versioned test ZIPs in `dist/` and one owner-approved installer at `stable/spline_maker-stable.zip`. Both folders are Git-ignored. Rebuild after pulling source on another machine and follow the promotion steps in `docs/BUILD.md`. Source is `extension/spline_maker/`; `spline-maker-starter/` is an old starter copy, not the active implementation.

From the repository root, set `$blender` to the local Blender 5.2.4 executable and run:

```powershell
New-Item -ItemType Directory -Force dist | Out-Null
& $blender --command extension build --source-dir extension/spline_maker --output-filepath dist/spline-1.1.0.zip
& $blender --command extension validate dist/spline-1.1.0.zip
```

Use the isolated-profile smoke-test command in `docs/BUILD.md`; it sets/restores `BLENDER_USER_RESOURCES` and installs into a fresh directory under `dist`, protecting the normal Blender profile. The entry point is `tests/blender/smoke_registration.py`, which runs the segment, region/spline, controls, Whole Move, transform and entry regression modules. Disable the previous build and restart Blender before installing a new ZIP for hands-on testing.

The owner selected GPL-3.0-or-later for Spline. Keep the license text in the repository and the installable ZIP in sync.
