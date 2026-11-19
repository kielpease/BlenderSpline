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

## Drawing gate

1. Start from Top Orthographic with cursor at a known location. Draw four corners and close. Confirm flat XY geometry and no duplicate endpoint.
2. Repeat in Front, Right, angled orthographic, and perspective views. Confirm plane through cursor facing starting view.
3. Orbit mid-draw. Confirm plane stays fixed; navigation works. Check nearly edge-on placement gives safe feedback.
4. Mix click corners with click-drag Bézier vertices. Check tiny cursor movement remains a corner; tangent direction and length follow a deliberate drag.
5. Hold/release Shift while placing points. Check 0/45/90/135-degree directions in plane coordinates and no jump to world axes.
6. Finish an open path, close a path, cancel a session, remove last point, undo/redo. Check no leftovers or changes to unrelated objects.

## Editing gate

1. Pick anchors/handles at several zoom levels; Shift-select and box-select vertices; click empty space.
2. Use right-click types on individual and multiple vertices. Check independent tangents remain part of the same spline.
3. Select adjacent segments. Check common endpoints are neither duplicated nor transformed twice.
4. Try Region mode on open and simple closed curves. Check unsupported loops/overlaps produce explicit feedback.

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
