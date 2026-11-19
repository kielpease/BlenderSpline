# Acceptance and validation plan

Record Blender version, extension version/commit, input/keymap setup, exact actions, expected behavior, actual behavior, and screenshots/video when useful. UI tests remain pending until performed in Blender; no code is implemented in this starter.

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
