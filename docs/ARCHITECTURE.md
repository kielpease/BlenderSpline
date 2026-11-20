# Proposed architecture

## Foundation

Use native Blender Bézier curve data as persistent source geometry. Implement custom interaction around it. Prefer a standard Blender extension with `blender_manifest.toml`, explicit registration, and no external runtime dependencies. Confirm APIs against Blender 5.2.4 LTS before implementation.

Keep document state (source curves and relevant settings) separate from transient interaction state (hover target, live preview, drag start, drawing plane during creation). Native curve data must remain usable if the add-on is disabled.

## Source layout

SM-001 implements the extension entry point, manifest, viewport UI, and background smoke test. SM-002 adds the isolated `extension/spline_maker/feasibility.py` probe.

| Path | Responsibility |
| --- | --- |
| `extension/spline_maker/__init__.py` | Register/unregister and lifecycle cleanup |
| `extension/spline_maker/blender_manifest.toml` | Extension metadata |
| `extension/spline_maker/operators/draw.py` | Drawing interaction state machine |
| `extension/spline_maker/operators/edit.py` | Vertex types and edit commands |
| `extension/spline_maker/tools.py` | Workspace tools and scoped bindings |
| `extension/spline_maker/selection.py` | Logical component selections and picking |
| `extension/spline_maker/transforms.py` | Selection-to-transform adapter and pivots |
| `extension/spline_maker/overlay.py` | Preview/highlight drawing and cleanup |
| `extension/spline_maker/ui.py` | Menus and visible controls |
| `extension/spline_maker/core/` | Plane projection, constraints, curve math, state |
| `tests/unit/` | Math and state tests outside Blender where practical |
| `tests/blender/` | Background registration/data smoke tests |
| `scripts/` | Build and focused validation helpers |

Do not create empty modules merely to match this table. Introduce each when its milestone needs it.

## Critical feasibility decisions

**Native editing versus custom interaction.** Native Edit Mode gives existing selection/transforms, but not all requested selection levels or tangent-only transforms. A custom tool gives more control but requires picking, gizmos, and careful undo integration. M0 should choose a hybrid or custom path using a working UI spike.

**Undo.** A long-running modal operator does not automatically provide a safe undo step per mouse click. Establish a tested transaction strategy; transient preview should not pollute saved data. Cancel must restore initial state. Undo may invalidate stored RNA references, so re-resolve or discard cached references safely.

**Selection.** Native curves lack mesh-like edge and face selection levels matching this specification. Logical segment/region selection needs an adapter. Native handles/anchors should not be selected incidentally in a way that defeats tangent-only transforms.

**Coordinates.** Handle world/local/object transforms explicitly, including nonuniform object scale. Use pixel-space picking tolerances. Constraints run in fixed drawing-plane coordinates. Never infer direction from world XY alone.

**Gizmos.** Prefer native gizmos when they match behavior. Use custom transform handling only where necessary; verify pivot, linked handles, cancellation, and navigation in the actual UI.

**Menu integration.** Add → Curve uses a menu callback. In Blender 5.2.4, `bpy.utils.register_tool(..., after={"builtin.primitive_cube_add"})` placed the probe inside the existing Object Mode Add group in the installed toolbar registry, with no patch to Blender internals. Viewport validation is pending. The menu and sidebar both launch the probe independently of the toolbar.

## SM-002 interaction approach

Use a hybrid approach for the probe. Native Curve Edit Mode provides point and handle selection state, and dedicated Spline Maker Move arrows invoke Blender’s native Translate operator. The probe tools own the Q/W bindings. Guarded entries in the Curve keymap give E/R priority over Blender’s Extrude and Rotate when a probe tool is active. For the tangent-only requirement, a native transform on an anchor selection can move the anchor. The probe uses an undoable custom operator with a viewport button and a sidebar action to transform offsets around each anchor.

Keep native Bézier storage and use the hybrid approach for vertex editing. Move supports native Bézier anchors and handles in single-object Edit Mode. The tangent probe uses a fixed 15° rotation around local Z and a 1.25× scale. Applying either step converts affected Vector handles to Free so their edited coordinates persist. Interactive rotate and scale drags, linked handles, and segment or region selection are outside this spike. A fully custom editor would need its own point picking and selection feedback. Reserve that work for behavior the native editor cannot provide.

Blender 5.2.4 LTS for Windows passed ZIP validation and background checks for tool activation, keymap ownership and cleanup, anchor invariance, individual-handle edits, and persistence after leaving Edit Mode. The owner verified the 0.2.3 tool controls, gizmos, and Undo in the [viewport test](TEST_PLAN.md#interaction-feasibility).

## SM-003 drawing transaction

The probe captures the cursor position and view rotation once. Mouse rays come from the live viewport. Their intersections use the captured plane and get stored in its local XY coordinates. The viewport draws temporary preview geometry with a [SpaceView3D draw handler](https://docs.blender.org/api/5.2/bpy.types.SpaceView3D.html#bpy.types.SpaceView3D.draw_handler_add).

The modal session owns a list of preview points. Ctrl+Z and Backspace remove the latest point from that list. Cancel discards the list and detaches the handler. Finish commits a native Bézier curve in one Blender undo step. This lets scene undo and redo act on the finished curve as a unit. Navigation events pass through to Blender. SM-006 captures an anchor on mouse press and commits on release. Dragging at least five pixels creates equal, opposite handles in the drawing plane. These are saved as native Aligned handles.

For SM-007, Shift rounds the angle from the previous anchor to the nearest 45° in plane coordinates and preserves the projected distance. The preview and mouse press use the same calculation. Once a press sets the anchor, the handle pull uses projected mouse movement from the unsnapped press location, so snapping does not change the handle direction or length.

On Finish, the curve object origin is the average of its anchors. Bézier coordinates are stored relative to that origin, preserving the world-space positions of anchors and handles on the drawing plane.

SM-008 tests closure against the projected first anchor within a 10-pixel radius. With at least three anchors, the hover preview joins the last anchor to the first using their existing handles. Clicking commits the same anchor list with the native cyclic flag. Enter, right-click, and the Finish button commit open curves.

## SM-009 vertex selection

The Q Select tool projects Bézier vertices and visible handles to screen coordinates using the edited object's world matrix. Click picks the nearest component within nine pixels. Shift-click toggles that component, and a box drag selects anchors. Selection uses Blender's native edit flags, which the existing Move, Rotate, and Scale controls can consume. The hover overlay uses Blender's cursor draw callback to read the pointer for the active viewport and resolves geometry on redraw. It follows Blender's handle visibility setting and runs on a single Bézier curve object in Edit Mode.

## SM-010 vertex types

The scoped right-click operator opens a Spline Maker vertex-type menu only while a Spline Maker Edit Mode tool is active on a single all-Bézier object. Sidebar buttons expose the same undoable operator. A selected anchor or individual handle identifies a whole vertex; conversions affect both tangents and preserve the original component selection. Right-click does not change selection or pick a new target. With no selection, type actions are disabled.

Corner, Smooth, Bézier, and Bézier Corner use Blender's native `curve.handle_type_set` Vector, Automatic, Aligned, and Free conversions, respectively. Temporary selection flags let the native operator change both handles; hidden vertices are temporarily deselected and all original flags restored afterward. No spline topology is changed. Blender recalculates automatic/vector tangents; manual Free conversion retains coordinates, and Aligned conversion preserves handle lengths while linking directions. Background checks verify those invariants against the installed 5.2.4 LTS API. The native operator is also used by the installed Blender Curve menus; see the [official operator reference](https://docs.blender.org/api/current/bpy.ops.curve.html#bpy.ops.curve.handle_type_set). Version-specific web documentation was unavailable during implementation; installed Blender provides the version-specific validation.

## 0.10.1 tangent control follow-up

Move arrows omit the GizmoGroup SCALE option so their display size stays independent of scene zoom, and use a smaller scale basis. Rotate and Scale replace the feasibility viewport step button with a view-facing dial and square-ended arrow. The existing sidebar steps remain available. A dedicated modal operator captures tangent coordinates/types by spline/point index, applies each update from that snapshot, and restores it on cancel or unregister. Confirming a drag uses one operator undo boundary. Vertex anchors stay fixed; each selected vertex uses its own anchor as pivot.

Interactive rotation acts in the view plane and accounts for object transforms. Scaling changes selected tangent lengths uniformly. Smooth tangents become manually linked Aligned tangents on editing; Corner tangents become Free. A single selected linked handle rotates its opposite tangent too, while a single-handle scale retains the opposite length. Independent tangents affect only the selected side. No geometry is changed merely by switching tools or pressing a control without dragging. Background checks cover the math and restoration; UI behavior awaits acceptance. These controls do not complete the later segment/region transforms or the full SM-015/SM-016 gates.

## 0.10.2 tool switching and gizmo ownership

Sidebar buttons call the same switch operator used by scoped Q/W/E/R shortcuts. Guarded priority bindings in both Curve and 3D View keymaps cover Blender and Industry Compatible configurations. The operator tags the viewport regions for redraw. All four workspace tools reference a single nonpersistent gizmo group through `bl_widget`. It reads the active tool and selection on each draw, hides all controls in Q, and switches axis arrows/rings/boxes together; separate persistent Move and tangent groups are removed.

Controls use Blender's built-in arrow, dial, and primitive gizmo types with global XYZ colors. Move still calls native Translate, including individual-handle movement. Rotate uses a ray/axis-plane intersection for the selected global axis, or view-plane rotation for the outer ring. Scale applies an axis stretch or a uniform center scale about each anchor. All matrices account for object transforms. A selected linked handle keeps the opposite tangent aligned; single-handle scale preserves the opposite local length. The existing discrete sidebar tangent steps remain available.

Shortcuts stay local to an active Spline Maker tool. The owner enters Curve Edit Mode with 1 using Industry Compatible; the extension does not override that key. Selecting Blender's native tools, including T Transform, leaves Spline Maker shortcuts. The sidebar indicates when its shortcuts are active and lets the user re-enter via Q Select. This avoids claiming native and custom tools have identical tangent/pivot semantics.

The installed Blender 5.2.4 scripts confirm workspace-tool widget registration and both keymap paths. Background tests verify switching parity, selection/geometry preservation, merged shortcut priority in both configurations, and lifecycle cleanup. The attempted separate-session UI investigation was stopped with physical Escape before corrected controls could be verified. No UI performance or completed transform milestone is claimed.

## 0.10.3 selection, handles, and planar Move

Selection overlays and the vertex-select gesture operate in all four Spline Maker tools on one all-Bézier Edit Mode object. The tool draws handle diamonds/guides independently of Blender's native handle-visibility dropdown, respecting the viewport Show Overlays switch and hidden vertices. Pressing a handle captures its owning point by spline/point index, its original tangent coordinates/types, selection flags, and a view-facing plane through the handle. Beyond the drag threshold it updates only that handle from the original snapshot. Cancel restores the point and selection; click-only and Shift-click selection retain their existing semantics. Dragging empty space boxes anchors in the current tool. Highlighted gizmos receive their input instead of starting a box.

The gizmo group records only transient viewport/group references for hit arbitration, with stale-reference guards and unregister cleanup. Direct handle hits take precedence over a highlighted gizmo. Transform gizmos and tangent steps now act only on selected anchors; selecting just a handle leaves its direct diamond available without creating an anchor gizmo. Manual Auto edits become Aligned, and manual Vector edits become Free. Linked direct editing preserves the opposite local tangent length.

`edit_drag.py` owns projection, point snapshots, direct-handle placement, and the Move operator. Global-axis/plane/view-plane drag deltas are converted through the object's inverse matrix. Every preview applies the current delta to the original coordinates, avoiding compounded motion and retaining native curve topology. Escape/right-click, tool changes, and unregister restore active sessions. The gizmo arrows/pads invoke this operator instead of native Translate. All gizmos hide during the Move preview, eliminating the simultaneous native-arrow offset display; they return after finish/cancel. This deliberately changes the drag display rather than claiming the old native ghost has been visually verified as fixed.

Background checks use real Blender curve data plus synthetic regions/events to validate selection and modal state logic. They do not establish actual gizmo hit dispatch, rendering, or undo history behavior in the UI.

## Later geometry

Profile generation may use Geometry Nodes or a controlled mesh generator. Choose after testing planar corner joins and alignment. Do not assume a rectangular Curve to Mesh sweep alone preserves wall thickness at every corner. Source curve remains editable; generated geometry is derived output. Height and width stay unit-aware settings independent of path vertex edits.

## Reference documentation

- Blender extension format: https://docs.blender.org/manual/en/5.2/advanced/extensions/getting_started.html
- Extension build CLI: https://docs.blender.org/manual/en/5.2/advanced/command_line/extension_arguments.html
- Use Blender's version-matched Python API documentation during implementation.
