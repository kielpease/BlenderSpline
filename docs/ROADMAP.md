# Development roadmap

Issue IDs below are proposed labels, not existing GitHub issue numbers. Complete dependencies in order. A milestone is accepted only when its tests pass in Blender's UI.

| Milestone                      | Result                                               | Dependencies                        |
| ------------------------------ | ---------------------------------------------------- | ----------------------------------- |
| M0: Foundation and feasibility | Installable shell and proven interaction approach    | None                                |
| M1: Drawing alpha              | Comfortable mixed corner/Bézier drawing              | M0                                  |
| M2: Editing alpha              | Predictable component picking and contextual editing | M1                                  |
| M3: Transform beta             | Q/W/E/R and all four selection levels                | M2                                  |
| M4: First usable release       | Reliable editing, packaging, documentation           | M3                                  |
| M6: Extended editing           | Insert/delete, break, attach, detach, weld, and Make Planar | M4                           |
| M5: Profile geometry           | Live height/width rendering                          | M6                                  |

## M0 — Foundation and feasibility

- **SM-001 — Installable extension shell.** Create manifest, register/unregister, Add → Curve → Draw Spline entry, sidebar placeholder, and build instructions. Done: install/enable/disable/re-enable without duplicate entries or errors. Select a license with the owner before setting manifest license metadata for distribution.
- **SM-002 — Interaction feasibility spike.** Prototype one native Bézier point, selectable handles, local Q/W/E/R activation, and transform gizmo interaction. Compare native Edit Mode integration with a custom tool. Done: record supported path and limitations in an architecture decision. Do not claim exact Max parity based on API availability.
- **SM-003 — Plane and undo feasibility spike.** Prove view-aligned projection in perspective/orthographic views, viewport navigation during drawing, and point-by-point undo/cancel behavior. Done: actual UI results documented. Investigate adding a tool to the existing Add flyout; document fallback if unavailable.

## M1 — Drawing alpha

- **SM-004 — Fixed drawing plane.** Capture orientation from starting view and depth from 3D cursor. Done: top/front/side/angled views work; orbiting does not rotate the captured plane.
- **SM-005 — Corner placement and preview.** Click points with clear preview, open-spline finish, and cancellation. Proposed finish: Enter or visible Finish; drawing right-click finishes an open spline. Done: no duplicate trailing vertex; cancel restores pre-session state.
- **SM-006 — Click-drag Bézier creation.** Apply a drag threshold; create balanced handles in the drawing plane. Done: straight and curved segments can be mixed continuously.
- **SM-007 — Shift direction constraints.** Snap direction from last committed vertex to 45-degree increments; preserve projected radial distance. Done: stable behavior across all view orientations and Shift press/release.
- **SM-008 — Closing and drawing undo.** Click first point with pixel-based close tolerance; require at least three vertices. Done: correct closing tangent, no duplicate first point, Backspace removes last committed point, undo/redo and cancellation satisfy the spec.

**Gate:** User draws a recognizable mixed straight/curved outline comfortably before editing scope expands.

## M2 — Editing alpha

- **SM-009 — Vertex and handle picking.** Hover and selection display, Shift add/remove, box selection, and empty-space deselection. Done: selection is accurate at different zoom levels and on transformed objects.
- **SM-010 — Right-click vertex types.** Corner, Smooth, Bézier, Bézier Corner. Done: tangent independence is predictable; menu does not confuse tangent breaking with topology splitting.
- **SM-011 — Segment selection.** Pick curved segment using evaluated screen-space distance, highlight it, select logical endpoints without losing segment identity. Done: shared endpoints move only once.
- **SM-012 — Spline and whole-curve selection.** Separate active object from selection of all geometry in that object. Per the owner's 0.12.5 refinement, 3 selects individual open/closed splines and auto-selects a sole path; Whole curve selects all source splines. Validated closed-interior picking supplements boundary picking; ambiguous interiors are not silently guessed.

## M3 — Transform beta

- **SM-013 — Tool/level controls.** Visible Q/W/E/R and scoped entry/exit keys. In supported Curve Edit Mode, 1/2/3 choose Vertex, Segment, or Spline, with All in the sidebar. 6 edits the active Bézier curve and 4 returns to Object Mode. Enter also finishes editing. Tool changes preserve selection and Q hides the gizmos.
- **SM-014 — Move.** Native or custom gizmo moves vertices with handles, individual handles, segments, individual splines, and all source splines together. Done: shared vertices transformed once; world-axis/plane deltas respect native object transforms; cancel and native Undo/Redo restore complete geometry. Whole curve Move in Edit Mode translates source geometry to stay within native Curve Edit undo; Object Mode provides native object transforms.
- **SM-015 — Rotate and scale.** Vertex mode rotates/scales tangent handles around their anchors. Segment/Spline/Whole levels transform selected source geometry about the average of unique selected anchors, with shared endpoints once. Handles retain their direct-drag controls; handle-only selection does not create a vertex gizmo. Done: documented multi-selection/pivot behavior, cancel and native Undo/Redo match UI tests.
- **SM-016 — Interaction integration.** Confirm cancel, undo/redo, axis constraints, navigation, and context menu around gizmos. Done: no transform jumps, swallowed navigation, or leaked keymaps.

## M4 — First usable release

- **SM-017 — Lifecycle and save/reopen.** Test multiple curve objects, scene changes, undo invalidation, tool exit, save/reopen, disable/re-enable. Done: no orphan overlays/handlers or data loss.
- **SM-018 — Package and user guide.** Version 0.18.0 completes the local installer and user guide. Clean installation passed on Blender 5.2.4 LTS for Windows. Public distribution awaits the owner's license decision. [User guide](USER_GUIDE.md) · [Test results](TEST_PLAN.md#sm-018-package-and-user-guide)

## M6 — Extended editing

1. **Menu polish and Add Vert** were accepted in 0.19.0. The test build centers the tool icons, defaults to Group rotation, adds coordinate copy and paste, and inserts on a picked Bézier segment with shape preservation. [Viewport check](BUILD.md#0190-menu-polish-and-add-vert)
2. **Remove Vert, Remove Segment, and Break Verts** are in the 0.20.0 test build. Delete follows Vertex and Segment levels while a Splines tool is active. The 0.20.1 follow-up hides unused and Vector handles and adds collapse and restoration before Attach and Weld. [Topology check](BUILD.md#0200-remove-and-break) · [Handle check](BUILD.md#0201-handle-visibility-collapse-and-restore)
3. **Attach and Weld** are in the M6 test build. Attach combines the selected objects in one operation and keeps their paths in place. Weld joins two open endpoints at their midpoint or closes one path. [Viewport check](BUILD.md#0210-attach-and-weld)
4. **Make Planar** and batch Attach were accepted in 0.22.0. Make Planar projects selected anchors and handles onto the recorded drawing plane or a plane facing the current view. [Viewport check](BUILD.md#0220-make-planar-and-batch-attach)
5. **Detach** is in the 0.23.0 test build. In **3 Spline**, it moves selected paths into a new curve object. [Viewport check](BUILD.md#0230-detach)

Later candidates include fillet/chamfer, outline, reverse, normalize, and advanced snapping.

## M5 — Profile geometry

The owner accepted **0.24.0**, which adds live centered Rectangle and Circle profiles with unit-aware dimensions and Rectangle Roll. **0.25.0** exposes Curve Resolution to smooth the sweep on curved spans and reuses the file's last-entered Rectangle Height and Width for new profiles. [Viewport checklist](BUILD.md#0250-curve-resolution-and-profile-defaults)

**0.26.0** keeps the Rectangle width through ordinary mitered corners and limits the extension at acute corners. Older profiles have a sidebar update action. [Viewport checklist](BUILD.md#0260-mitered-profile-corners)

Next are base/center/top and inside/center/outside alignment, overlap handling at tight bends and path intersections including T-junctions, and material behavior.

## 1.0 release preparation

The 0.26.4 development build adds a Bézier icon to **Add → Curve → Draw Spline** and includes the M6 editing tools and M5 live profiles documented in the [user guide](USER_GUIDE.md).

- Review 0.26.4 in a clean Blender profile with the Default and Industry Compatible keymaps. Use the [release gate](TEST_PLAN.md#release-gate) and [viewport checks](BUILD.md#0264-draw-spline-menu-icon).
- Confirm the distribution license and apply it to the repository and Blender manifest.
- Build and validate the approved 1.0 ZIP, confirm a clean install, and use that artifact for the GitHub release.

## Suggested GitHub labels

`drawing`, `selection`, `transforms`, `ui`, `geometry`, `bug`, `needs-user-test`, `blocked`, `documentation`.

Track status as Backlog → Ready → In progress → Needs user test → Done. Avoid time estimates until M0 resolves the highest-risk interaction assumptions.

## Current status

- **SM-009 — Done:** owner accepted 0.9.1 after verifying vertex squares and handle diamonds using the sidebar Q Select button. Earlier selection/Undo checks are recorded in TEST_PLAN.md; box dragging has background coverage only.
- **SM-010 — Done:** owner confirmed all four vertex types and Ctrl+Z in 0.10.0. Subsequent interaction fixes were accepted in 0.10.3; background checks cover both default and Industry Compatible shortcut priority.
- **0.10.3 interaction follow-up — Done:** owner accepted the build on 2026-11-20, reporting that everything worked wonderfully. This accepts all-tool box selection, direct tangent diamonds, vertex-only gizmos, and planar Move controls. The feedback is overall viewport acceptance, not a separately itemized test log.
- **SM-011 — Done:** owner verified segment highlighting, selection, Move, returning to Vertex editing, and the centered gizmo in 0.11.1. Segment Rotate/Scale was subsequently accepted with SM-015 in 0.15.0.
- **SM-012 — Done:** owner accepted the refined 0.12.5 Spline selection behavior after earlier reports that selection worked. This is overall viewport acceptance rather than an itemized result for every geometry case. Whole Move is accepted in 0.14.0; SM-015 transforms were subsequently accepted in 0.15.0.
- **0.12.1 follow-up — Needs user test:** owner reported 2/3 requiring sidebar Q entry, visible curve normals, and dark unselected curves. Adds direct Edit Mode 2/3 entry, a native normals checkbox, and a bright session-color overlay available in native Curve Edit tools too. Background entry/keymap/lifecycle checks pass; physical shortcuts and rendering await confirmation.
- **0.12.2 exit follow-up — Needs user test:** adds Finish Editing → Object Mode and scoped Esc exit, addressing confusion between Whole curve selection and Object Mode. Background checks preserve geometry/object selection and reset native tools across all Q/W/E/R × Vertex/Segment/Region/Whole combinations. Physical Esc cancellation/exit and panel use await acceptance.
- **SM-013 — Done:** owner calls 0.13.0 a success and explicitly confirms Move works well in 1 Vertex, 2 Segment and 3 Spline. This is overall task acceptance, not a separately itemized result for every tool/keymap case. Background integration checks cover all four levels, every Q/W/E/R transition, selection/geometry preservation, and gizmo visibility state.
- **SM-014 — Done:** owner confirms Move in 0.14.0 works as intended, accepting the added Whole curve action after earlier Vertex/Segment/Spline acceptance. This is overall acceptance rather than an itemized result for every constraint/undo case. The Edit Mode geometry path keeps object transforms unchanged and has background coverage for axes/planes, hidden points, parent transforms, cancellation and native Undo/Redo.
- **0.14.1 Segment box correction — Done:** owner confirms it works great. Segment boxes select any touched/crossed curve span in either drag direction; Shift adds. Spline/Whole enclosure rules stay in place. This is overall acceptance rather than a per-case test report.
- **SM-015 — Done:** owner reports Move, Rotate and Scale work great for 1/2/3/4 in 0.15.0. This is overall transform acceptance rather than a separately itemized result for every control/pivot case. The reported Select re-entry issue is tracked below.
- **0.15.1 Select entry correction — Done:** owner confirms the previously mentioned fixes work well. 1/6 enter a single selected editable Bezier curve with Q Select active, and Q can enter Select from native Curve Edit tools. This is overall acceptance rather than a per-case report.
- **0.15.2 XY scale control — Done:** owner confirms it works great and requests commit/push plus a home-session handoff. This accepts the offset XY square overall; no per-case viewport log was supplied. Prior Move/Rotate/Scale and Select entry acceptance remains in effect.
- **0.15.8 Bézier closure — Done:** owner accepted click-drag handles on the closing vertex and requested the next step.
- **SM-016 interaction integration — 0.16.0 candidate:** native navigation reaches active drag handlers, and transforms keep their preview while the viewport changes. The first drag after entering Edit Mode has a native Undo checkpoint. See the [viewport check](BUILD.md#0160-interaction-integration-viewport-check).
- **SM-017 lifecycle and save/reopen — 0.17.0:** background and isolated Industry Compatible viewport checks passed on Blender 5.2.4 LTS. Committed curves survive save/reopen, and switching tools or scenes clears live previews. Disable/re-enable restores native Select Box and registers each callback once. [Viewport check](BUILD.md#0170-lifecycle-viewport-check)
- **0.15.3 edit controls — Needs user test:** Center Vertex Move, add optional Vertex Group rotation, and put selection levels at the top with 4 All and Enter to finish. The owner reported exploratory moves across viewport orientations, vertices, segments and splines without major issues.
- **Make Planar:** Implemented in the M6 0.22.0 test build.

- **0.12.3 workflow follow-up - Done:** owner accepts the version, explicitly confirming spline color and 4 returning to Object Mode with the Edit menu disappearing. The owner previously reported selection working. This is overall version acceptance, not an itemized report for every drawing or selection test.
- **0.12.4 Edit entry follow-up - Done:** owner confirms pressing 6 works well. It enters Q Select / Vertex editing for one selected editable Bezier curve. Meshes, unsupported curves, and multi-object selections retain native behavior; 5 stays native. The sidebar button was not separately reported.
- **0.12.5 Spline selection refinement - Done:** owner reports it works well and requests the next task. This accepts the revised Spline selection workflow overall; no separate per-case test log was supplied. Attach remains deferred.
