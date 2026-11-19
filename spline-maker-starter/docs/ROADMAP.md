# Development roadmap

Issue IDs below are proposed labels, not existing GitHub issue numbers. Complete dependencies in order. A milestone is accepted only when its tests pass in Blender's UI.

| Milestone | Result | Dependencies |
| --- | --- | --- |
| M0: Foundation and feasibility | Installable shell and proven interaction approach | None |
| M1: Drawing alpha | Comfortable mixed corner/Bézier drawing | M0 |
| M2: Editing alpha | Predictable component picking and contextual editing | M1 |
| M3: Transform beta | Q/W/E/R and all four selection levels | M2 |
| M4: First usable release | Reliable editing, packaging, documentation | M3 |
| M5: Profile geometry | Live height/width rendering | M4 |
| M6: Extended editing | Insert/delete, attach, weld, and related operations | M4; geometry integration follows M5 |

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
- **SM-012 — Whole curve and closed region selection.** Separate active object from selection of all geometry in that object. Region picking initially supports simple planar closed loops only. Done: open curves disable region selection clearly; overlapping/unsupported regions are not silently guessed.

## M3 — Transform beta

- **SM-013 — Tool/level controls.** Visible Q/W/E/R and 1–4 controls plus scoped keys. Done: tool changes preserve selection and Q hides the gizmo.
- **SM-014 — Move.** Native or custom gizmo moves vertices with handles, individual handles, segments, regions, and whole curves. Done: shared vertices transformed once; native object transforms respected.
- **SM-015 — Rotate and scale.** Vertex-only mode rotates/scales tangent handles around their anchors by default. Segment/region mode transforms selected geometry about selection center. Individual-handle mode uses anchor as pivot. Done: documented multi-selection/pivot behavior matches UI tests.
- **SM-016 — Interaction integration.** Confirm cancel, undo/redo, axis constraints, navigation, and context menu around gizmos. Done: no transform jumps, swallowed navigation, or leaked keymaps.

## M4 — First usable release

- **SM-017 — Lifecycle and save/reopen.** Test multiple curve objects, scene changes, undo invalidation, tool exit, save/reopen, disable/re-enable. Done: no orphan overlays/handlers or data loss.
- **SM-018 — Package and user guide.** Build an installable extension ZIP, version it, document known limits and test steps. Done: clean-install test passes on Blender 5.2.4 LTS, and release status accurately distinguishes tested features from plans.

## M5 — Profile geometry (deferred)

Live rectangular profile with Height/Width; unit-aware input; base/center/top and inside/center/outside alignment. Validate 8 ft × 1 ft walls. Keep source spline editable. Solve corner joins, miter limits, winding, curved paths, intersections, normals, materials, and save/reopen. Implement simple planar cases first; arbitrary 3D paths are a separate extension of scope.

## M6 — Extended editing (deferred)

Insert vertex preserving Bézier shape; delete vertex with explicit resulting topology; attach/detach splines across object transforms; weld compatible endpoints with tolerance; split/break topology. Later candidates: fillet/chamfer, outline, reverse, normalize, and advanced snapping. Each becomes a separately specified issue.

## Suggested GitHub labels

`drawing`, `selection`, `transforms`, `ui`, `geometry`, `bug`, `needs-user-test`, `blocked`, `documentation`.

Track status as Backlog → Ready → In progress → Needs user test → Done. Avoid time estimates until M0 resolves the highest-risk interaction assumptions.
