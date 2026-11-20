# Acceptance and validation plan

Record Blender version, extension version/commit, input/keymap setup, exact actions, expected behavior, actual behavior, and screenshots/video when useful.

## Foundation gate

For SM-001, run the background installation and registration smoke test and complete the viewport check in [Build and test](BUILD.md). Record the background and visual results separately.

SM-001 passed on Blender 5.2.4 LTS for Windows with Spline Maker 0.1.0.

- Background: The ZIP installed in an isolated profile. Enable, disable, and re-enable passed, including registration cleanup and a single Add → Curve menu callback after re-enable.
- Viewport: The owner confirmed the menu entry and sidebar panel, the status message without object creation, and that both entries disappeared on disable and returned once on re-enable.

## Interaction feasibility

SM-002 viewport results for Spline Maker 0.2.3 on Blender 5.2.4 LTS for Windows:

- The owner confirmed Q Select, W Move, E Rotate, and R Scale work in the vertex editing workflow and that Ctrl+Z reverses each edit. The 0.2.3 viewport retest resolved the earlier missing and mismatched gizmos.
- The owner observed that 1 entered vertex Edit Mode and 4 selected the whole curve, while 2 and 3 did not provide curve selection. SM-002 registers Q/W/E/R only. The number-key behavior in the test setup has not been attributed to a specific keymap.
- Background results are recorded in the [architecture decision](ARCHITECTURE.md#sm-002-interaction-approach). The viewport report covers the tool and Undo sequence. Independent handle picking and switching back to Blender's own shortcut and gizmo controls were not separately reported.

## Drawing plane and undo feasibility

SM-003's Blender 5.2.4 LTS Windows background check passed orthographic and perspective ray math, near-parallel and behind-eye rejection, point removal and cancellation, native Bézier output, and toolbar Add flyout membership.

The owner confirmed straight corners, the light-blue preview, pan during drawing, and right-click to finish in 0.3.0. The owner verified that Industry Compatible zoom stays active during drawing in 0.3.1. In 0.3.2, the background test finishes a new curve and then checks Move gizmo eligibility, Rotate, and Scale in Edit Mode. The owner reported that 0.3.2 worked in the viewport after this retest. Individual results for the other [SM-003 viewport checks](BUILD.md#sm-003-viewport-check) were not separately reported.

The owner confirmed the crosshair worked in 0.3.3.

## SM-004 fixed drawing plane

The 0.4.0 background test on Blender 5.2.4 LTS for Windows uses Blender's viewport projection helpers with top, front, side, and angled view matrices. It verifies orthographic and perspective placement through an offset 3D cursor and checks that the same world point maps to the same plane coordinate after orbiting. The owner confirmed drawing across different views, first-click placement from the left toolbar in 0.4.1, and the two-right-click Finish and Exit sequence in 0.4.2.

## SM-005 corner placement and preview

The 0.5.0 background checks cover Finish and Cancel hit regions, consecutive duplicate rejection, the two-point minimum, one open Bézier result on Finish, and cancellation leaving the scene and selection unchanged. The owner confirmed the [viewport check](BUILD.md#sm-005-viewport-check), including the corner preview, open spline finish, and cancellation.

## SM-006 click-drag Bézier creation

The 0.6.0 background checks on Blender 5.2.4 LTS for Windows verify the drag threshold, preview curvature, a mixed native Bézier spline, equal and opposite Aligned handles, and Rotate on a selected Aligned anchor. The owner confirmed the [viewport check](BUILD.md#sm-006-viewport-check) for click-drag Bézier creation.

## SM-007 Shift direction constraints

The 0.7.0 background checks on Blender 5.2.4 LTS for Windows cover all eight directions near snap boundaries, preservation of distance, first-point placement, consistent results across viewport orientations and after orbiting, and unchanged handle drag offsets. The owner confirmed Shift snapping in the viewport.

The 0.7.1 background checks confirm the new origin matches the average of the anchors and preserves world-space anchor and handle coordinates. The owner confirmed the centered whole-spline Move gizmo in the viewport.

## SM-008 closing and drawing undo

The 0.8.0 background checks on Blender 5.2.4 LTS for Windows exercise the modal event logic for the close tolerance, three-anchor minimum, Backspace and Ctrl+Z point removal, and cancellation of a close click released outside the target. They verify that the finished cyclic spline has no duplicate endpoint and preserves its Aligned and Vector closing handles. The owner confirmed that the [SM-008 viewport behavior](BUILD.md#sm-008-viewport-check) worked as intended.

## Drawing gate

1. Start from Top Orthographic with cursor at a known location. Draw four corners and close. Confirm flat XY geometry and no duplicate endpoint.
2. Repeat in Front, Right, angled orthographic, and perspective views. Confirm plane through cursor facing starting view.
3. Orbit mid-draw. Confirm plane stays fixed; navigation works. Check nearly edge-on placement gives safe feedback.
4. Mix click corners with click-drag Bézier vertices. Check tiny cursor movement remains a corner; tangent direction and length follow a deliberate drag.
5. Hold/release Shift while placing points. Check 0/45/90/135-degree directions in plane coordinates and no jump to world axes.
6. Finish an open path, close a path, cancel a session, remove last point, undo/redo. Check no leftovers or changes to unrelated objects.

## Editing gate

The 0.9.0 SM-009 background checks on Blender 5.2.4 LTS for Windows validate click and Shift-click selection, empty-space deselection, anchor-only box selection, hidden components, and the tool guard. The tests use an object with translation, rotation, and nonuniform scale at two projection scales. The owner confirmed selection toggling and Undo, then verified the square and diamond in 0.9.1 after clicking the sidebar Q Select button. An isolated Industry Compatible viewport test verified rendered pixels for both hover markers and the selected-handle marker after pressing Q from Spline Maker Move. Pressing Q from Blender's Move tool activates Blender's Select Box. Box-drag behavior was covered by background checks and was not separately reported in the owner's viewport.

1. Pick anchors/handles at several zoom levels; Shift-select and box-select vertices; click empty space.
2. Use right-click types on individual and multiple vertices. Check independent tangents remain part of the same spline.
3. Select adjacent segments. Check common endpoints are neither duplicated nor transformed twice.
4. Try Region mode on open and simple closed curves. Check unsupported loops/overlaps produce explicit feedback.

## SM-010 vertex types

Version 0.10.0 passes package validation and the background smoke test on Blender 5.2.4 LTS for Windows. Checks cover tool-context guards, disabled actions without selection, multiple vertices including a selected handle owner, all four handle-type mappings, anchor and topology invariance, manual handle length preservation, independent tangent edits, hidden vertex protection, component selection preservation, and registration cleanup. SM-009 was accepted by the owner on 2026-11-20.

The owner confirmed all four vertex types and Ctrl+Z in 0.10.0, accepting SM-010. They reported oversized Move arrows and missing usable Rotate/Scale controls.

Version 0.10.1 adds a view-facing rotation ring and a square-ended uniform tangent-scale arrow, removes zoom-dependent display scaling, and accepts selected handles of all four types. Background checks cover single-handle eligibility, linked and independent rotation, scale, repeated updates from a fixed snapshot, nonuniform object transforms, anchor/neighbor invariance, and restoration of coordinates/types. Physical drag, screen size, and drag Undo/redo remain unverified: Computer Use was stopped with Escape during viewport investigation before the revised build was tested.

## 0.10.2 switching and redraw regression

The owner reported keyboard/sidebar differences and gizmos refreshing only after viewport navigation in 0.10.1, preferring Blender's standard axis appearance. They confirmed individual Bézier-handle Move worked. The 0.10.2 background suite on Blender 5.2.4 LTS for Windows passes all 16 tool transitions through the shortcut and sidebar operator paths, preserves component selection and geometry, checks merged Q/W/E/R priority in both Curve and 3D View maps with the installed Industry Compatible preset, and verifies cleanup. Existing tangent/vertex/drawing checks also pass.

Tool-owned rendering, live switching without navigation, axis dragging, Cancel and Undo/redo still require the [0.10.2 UI procedure](BUILD.md#0102-tool-switching-regression-check). A separate Blender session was prepared for physical testing, but Computer Use was stopped with Escape before the revised controls could be exercised. Background tests do not establish visual or responsiveness acceptance.

## 0.10.3 selection and direct manipulation

ZIP validation and the full background suite pass on Blender 5.2.4 LTS for Windows. Real curve data and synthetic modal events cover anchor box selection without changing Q/W/E/R, handle-drag versus box branching, stationary handle owners, cancel restoration of geometry/types/selection, independent/linked/Auto/Vector handle behavior, repeated noncompounding updates, and Move constraints/rollback on rotated/nonuniformly scaled objects. Both default and Industry Compatible keymap tests continue to pass. Gizmos now require selected anchors; handle-only selections use direct manipulation.

The owner accepted the 0.10.3 interaction follow-up on 2026-11-20, reporting that everything worked wonderfully. This is overall acceptance of the [viewport workflow](BUILD.md#0103-selection-and-direct-handle-test); no separate per-case results were supplied. The background checks remain distinct from the owner's hands-on acceptance. The earlier pending 0.10.1/0.10.2 interaction reports are superseded by this acceptance.

## SM-011 segment selection (0.11.0)

Package validation and the complete background suite pass on Blender 5.2.4 LTS for Windows. New checks cover curved midpoint picking at three projection scales on transformed geometry; separate spline identities; Shift toggle and deselection; box enclosure; separated segments without an inferred middle segment; cyclic closing edges; hidden endpoints; unique shared endpoints under translation; preserved identity across Q/W/E/R and direct handle data edits; and disabled segment Rotate/Scale. Native Edit Mode Undo and Redo restore the exact logical selected segment after explicit undo boundaries. Registration/cleanup checks include the transient level property and scoped 1/2 bindings.

The owner accepted SM-011 after verifying segment highlighting, selection, gizmo Move, and switching back to Vertex for further editing. This is acceptance of those reported behaviors, not a separately itemized result for every case in the [viewport procedure](BUILD.md#sm-011-segment-selection-test).

The owner accepted the centered Move gizmo in 0.11.1. Vertex-mode positioning and segment Rotate/Scale scope are unchanged.

## SM-012 whole curve and closed regions (0.12.0)

The package and full background suite pass on Blender 5.2.4 LTS for Windows. New checks cover valid separate planar loops with an open spline, curved loop sampling/interior classification, native Region and Whole geometry selection Undo/Redo, Shift-toggle and box enclosure via synthetic projection, boundary endpoint union/center, object activation distinct from geometry selection, geometry-preserving whole selection, and disabled deferred transforms. Tests verify ray-plane picking through tilted/nonuniform object transforms, cache invalidation after handle edits, and rejection of open, collinear, self-intersecting, nonplanar, overlapping, nested and touching boundaries. Regions on different planes that overlap in projection report ambiguity without changing selection.

Physical picking/hover, drawing default level, disabled-button layout, actual gizmo dispatch, Region Move and UI operator Undo grouping still need the [SM-012 viewport procedure](BUILD.md#sm-012-whole-curve-and-region-test). Background data and projection tests are not UI verification.

## 0.12.1 keyboard entry and curve display

The owner reported that native 1/4 worked but 2/3 required clicking sidebar Q Select. New background checks on Blender 5.2.4 LTS cover direct Segment entry from native Select Box and Region entry from native Move, the resulting active Spline Maker tool/level, entry rejection in Object Mode, merged 2/3 keymap priority with Industry Compatible, and cleanup of the display properties/handler. The complete suite, native Region/Whole Undo/Redo, package validation, and diff checks pass.

The [0.12.1 viewport check](BUILD.md#0121-keyboard-and-visibility-check) remains pending. Background tests do not establish physical key delivery, color/contrast, overlay ordering, or the checkbox's visual effect on normals.

## 0.12.2 explicit editing exit

The owner reported being stuck in component editing after choosing Whole curve and Q Select. Version 0.12.2 exposes Finish Editing → Object Mode and adds a guarded Esc binding in Curve and 3D View keymaps. The full suite and ZIP validation pass on Blender 5.2.4 LTS for Windows. New background checks exercise button and shortcut operator paths across all four tools and four selection levels, verify unchanged native curve geometry/object lists, keep the same selected active object, reset both Object/Edit tools to Select Box, reset the transient level, and reject the shortcut in native Edit tools and Object Mode. Lifecycle checks verify removal of the Esc bindings.

The [0.12.2 viewport check](BUILD.md#0122-finish-editing-test) remains pending, especially physical event priority: Esc during a modal drag must cancel only the drag, and the next Esc must leave Edit Mode. Operator/background checks do not establish that UI dispatch sequence.


## 0.12.3 finish, Object Mode visibility, and mode keys

Validation and the complete suite pass on Blender 5.2.4 LTS for Windows. Drawing checks activate the actual Draw workspace tool before open Finish and closing-click modal logic, then verify Select Box is active. Display eligibility checks cover unselected/selected/hidden curve objects and inclusion of edit-hidden points in Object Mode source sampling. Keymap checks verify 4/Esc exit, removal of 4/Whole, and no extension 5/6 bindings. Existing selection, geometry, native Undo/Redo and edit-exit checks continue to pass.

The owner reports selection working. Actual finish/edit/reselect click dispatch, rendered Object Mode colors/depth behavior, and physical key priority in the owner's keymap remain pending under the 0.12.3 procedure in BUILD.md. Background checks are not UI verification.

The owner subsequently accepted 0.12.3 and explicitly confirmed spline color and 4 returning to Object Mode with the menu disappearing. Selection had already been reported working. This is overall acceptance, not a separately itemized execution of every test above.

## 0.12.4 Edit Spline entry

ZIP validation and the complete background suite pass on Blender 5.2.4 LTS for Windows. Background checks cover entering Q Select / Vertex Edit Mode, returning with the shared 4 exit operator, repeating entry without geometry/object changes, entry from a native Edit tool and Whole level, and rejection for no selection, meshes in Object/Edit Mode, mixed curve types, and multiple selected objects. Lifecycle checks cover 6 bindings in Object Mode, Curve, and 3D View, plus merged shortcut priority with the installed Industry Compatible preset. Physical 6 delivery and the Object Mode Edit Spline button still require the procedure in BUILD.md.

The owner subsequently confirms pressing 6 works well. The sidebar button and unsupported-context cases were not separately reported.

## 0.12.5 Spline level

ZIP validation and the complete background suite pass on Blender 5.2.4 LTS for Windows. New checks cover sole-spline auto-selection for open, closed, nonplanar, self-intersecting, and one-anchor paths; repeating 3; native selection Undo/Redo; retention on returning to Vertex; geometry invariance; and rejection of partially hidden paths. Multi-spline checks cover independent open-path picking, centered Move eligibility, Shift toggles, whole-path box enclosure, nonplanar boundary picking, and no arbitrary automatic selection when multiple paths exist. Closed-loop validation and ambiguity tests remain in place for interior picking. Physical 3 entry, highlights, picking, boxes and Move require the 0.12.5 procedure in BUILD.md.

The owner subsequently reported that 0.12.5 works well and requested the next task. This accepts the Spline selection refinement overall; individual cases above were not separately reported.

## SM-013 tool/level integration (0.13.0)

ZIP validation and the complete background suite pass on Blender 5.2.4 LTS for Windows. New checks use real native curve data under translation, rotation and nonuniform scale. They cover direct entry into each level from a native Edit tool; availability of all level buttons in the panel's draw path; all 16 Q/W/E/R transitions per level through keyboard/button operators; unchanged selection flags, level, geometry and handle types; Q disabling transform operators; native-tool shortcut guards; and Object Mode/mesh exclusion. Synthetic gizmo controls verify the actual draw-preparation method's visibility state and world-space origin, including all controls hidden for Q. Merged Industry Compatible checks now include 1 entry. Physical key delivery, panel layout, redraw timing and rendered gizmos require the SM-013 procedure in BUILD.md.

The owner subsequently called 0.13.0 a success, explicitly confirming Move works well in 1 Vertex, 2 Segment and 3 Spline. SM-013 is accepted on that overall report; no separate per-case results were supplied. Whole curve Move and non-vertex Rotate/Scale are still pending implementation in SM-014/015.

## SM-014 Whole curve Move (0.14.0)

The owner already accepts Move in Vertex/Segment/Spline. The audit found the separate Whole curve action disabled; this build adds it to the shared geometry-translation implementation. ZIP validation and the complete background suite pass on Blender 5.2.4 LTS for Windows.

New native-data/synthetic-event checks exercise multiple open splines and every handle type, including an edit-hidden point. Under parent and object rotation/nonuniform scale, XYZ/XY/XZ/YZ/view-plane drags translate every anchor and handle by the same world delta while keeping the object/parent/child matrices unchanged. Repeated preview, handle types, selection flags, no-op release, Esc/right-click/Ctrl+Z/window-deactivation cancellation, tool-change/unregister rollback, cleared-selection guards and native Curve Edit Undo/Redo pass. Gizmo-state integration now expects Whole Move to be visible in W and hidden in Q. The added Whole interaction and physical undo grouping still need the 0.14.0 viewport procedure in BUILD.md.

An installed-version diagnostic verified why source geometry is moved: changing object location in Curve Edit Mode was not undone by native Curve Edit undo pushes. Object Mode remains the native object-transform workflow.

The owner subsequently confirms Move in 0.14.0 works as intended. SM-014 is accepted on that overall report; individual constraint/undo cases were not separately reported.

## 0.14.1 Segment crossing-box selection

ZIP validation and the complete background suite pass on Blender 5.2.4 LTS for Windows. Focused checks cover horizontal/vertical crossings with both endpoints outside, exact edge/corner touches, degenerate sampled edges, and a bounding-box overlap that does not intersect the rectangle. Native curve checks use a small box around a curved segment's middle at three zoom levels under a rotated/nonuniform transform, both box directions, Shift-add, empty-space replace/add, hidden endpoints, empty projected spans and sparse samples crossing a box. Existing native selection Undo/Redo and the full interaction suite pass. Physical drag selection and the changed panel hint need the 0.14.1 procedure in BUILD.md.

The owner subsequently confirms the 0.14.1 correction works great. Segment crossing-box selection is accepted on that overall report; individual cases were not separately reported.

## SM-015 selection-center Rotate/Scale (0.15.0)

New checks use a parented curve under rotation and nonuniform scale, with multiple open splines. For Segment/Spline/Whole they verify unique selected endpoints and the average-anchor pivot, world XYZ rotations and scales, uniform scaling, transformed anchors and Free handles, unchanged unselected geometry/object matrices, stable flags/types, and no compounded preview. Whole includes edit-hidden points. Synthetic modal tests exercise all axis/view rings and axis/center scale controls, no press jump, preview-owned gizmo hiding, Esc/right-click/Ctrl+Z/window-deactivation rollback, returning to identity, no-op release, tool-change/unregister rollback, empty selections and unavailable orthographic axes.

Native Curve Edit Undo/Redo restores geometry and flags for committed synthetic drags and discrete step actions at each composite level. A separate native-data check preserves Vector/Auto/Aligned/Free types through whole-geometry uniform scaling and Undo. ZIP validation, the focused SM-015 checks and the complete background suite pass on Blender 5.2.4 LTS for Windows, including existing vertex tangent and all Move/selection/lifecycle regressions. Physical controls and operator undo grouping need the 0.15.0 procedure in BUILD.md.

The owner subsequently confirms Move/Rotate/Scale work great for 1/2/3/4. SM-015 is accepted on this overall report; individual control cases were not separately reported. Select re-entry is the separate 0.15.1 correction.

## 0.15.1 Q Select entry regression

ZIP validation, focused entry checks and the complete background suite pass on Blender 5.2.4 LTS for Windows. Tests resolve operators from actual merged keymap items with their polls/properties in default and Industry Compatible configurations. Repeated Object Mode 1/6 entry after native/custom exits must activate Select and Vertex immediately. Native mode entry followed by 1/6 must also activate Select. Q from native Select Box/Move or custom W/E/R activates Select, preserves geometry and composite level/selection, and sets the panel draw path's Q button to pressed. No-selection and mesh Object/Edit contexts reject owned entry actions. Lifecycle tests check every new binding is removed on disable/re-enable. Physical key dispatch and the actual pressed button still need the 0.15.1 viewport procedure.

The owner subsequently confirms the previously mentioned entry fixes work well, accepting 0.15.1 overall.

## 0.15.2 XY scale square

ZIP validation, focused control/transform checks and the complete background suite pass on Blender 5.2.4 LTS for Windows. Synthetic gizmos exercise the actual setup method and confirm SCALE/XY operator routing, positive diagonal offset, and visibility only in Segment/Spline/Whole Scale. Native-data/synthetic-event tests extend all composite transform levels with XY scaling on parented/nonuniformly scaled objects, including nonzero Z geometry. They verify the no-jump offset press, equal world X/Y factors, unchanged world Z, repeated preview, cancel and native Curve Edit Undo/Redo. An edge-on XY view rejects the drag. Physical square size, offset, hit testing and feel require the 0.15.2 viewport procedure.

The owner subsequently confirms 0.15.2 works great, accepting the XY scale control overall and requesting a committed home-session handoff. Individual edge cases were not separately reported.

## SM-016 resume procedure

Resume from the accepted 0.15.2 baseline. Existing synthetic tests establish rollback and native undo data, but not physical event routing or one UI history entry per gesture.

1. Check orbit/pan/zoom while Q/W/E/R are idle, then during box selection, direct-handle drags and active Move/Rotate/Scale. Code inspection shows transform modals consume unhandled events; investigate dispatch and stable projection before changing that policy. Navigation must not create geometry jumps or commits.
2. For each level, confirm a completed gesture forms one native Undo step and Redo restores it. First Esc cancels the current gesture and restores geometry/selection; the next Esc exits editing. Check right-click cancellation versus the idle vertex-type menu.
3. Recheck XYZ, plane/view and XY scale controls on transformed/parented objects while changing the view. Tool switches and native tool exit must restore/cancel owned previews without stale gizmos or lost selection.
4. Verify default/Industry Compatible shortcut scope, repeated Object/Edit entry, context menus and disable/re-enable cleanup. Record actual viewport results separately from background checks. Lifecycle/save-reopen beyond this integration belongs to SM-017.

## Transform gate

1. Q shows selection without gizmo. W/E/R activate gizmos without moving geometry until manipulated.
2. Move anchor: both handles follow. Move handle: correct linked/independent behavior.
3. Rotate/scale one vertex: handles change around fixed anchor. Repeat with multiple vertices and documented pivots.
4. Transform segment, region, and whole curve. Repeat after object rotation and nonuniform scale.
5. Cancel each transform and undo/redo. Switch tools/levels without losing intended selection.
6. Leave Spline Maker context. Confirm normal Blender shortcuts remain intact.

## Release gate

Save/reopen .blend, multiple objects, scene changes, delete active object, undo through object creation, disable/re-enable, clean ZIP install. Confirm handlers, keymaps, menus, and overlays are cleaned up.

## Meaningful automated checks

- Plane/ray intersections including parallel rays.
- Angle constraints around boundaries and all quadrants.
- Transform affected-set union for adjacent segments.
- Bézier vertex/handle transformation invariants.
- Background Blender register/unregister, native data creation, save/reopen as relevant.
- Extension package validation and build when available.

Automated/background checks do not establish correctness of mouse picking, cursor feedback, gizmos, or navigation. Each release must list manual tests actually run and remaining limitations.
