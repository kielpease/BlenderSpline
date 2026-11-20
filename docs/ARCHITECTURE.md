# Architecture and implementation decisions

## Foundation

Use native Blender Bézier curve data as persistent source geometry. Implement custom interaction around it. Prefer a standard Blender extension with `blender_manifest.toml`, explicit registration, and no external runtime dependencies. Confirm APIs against Blender 5.2.4 LTS before implementation.

Keep document state (source curves and relevant settings) separate from transient interaction state (hover target, live preview, drag start, drawing plane during creation). Native curve data must remain usable if the add-on is disabled.

## Source layout

The extension retains its original feasibility module names where they are registered identifiers. Current responsibilities are:

| Path | Responsibility |
| --- | --- |
| `extension/spline_maker/__init__.py` | Register/unregister and lifecycle cleanup |
| `extension/spline_maker/blender_manifest.toml` | Extension metadata |
| `extension/spline_maker/drawing_probe.py` | Drawing state, modal operator and drawing tool |
| `extension/spline_maker/drawing_plane.py` | Fixed-plane projection and placement constraints |
| `extension/spline_maker/vertex_types.py` | Vertex types and context menu |
| `extension/spline_maker/feasibility.py` | Edit workspace tools, mode entry/exit, scoped keys, pivots and Edit panel |
| `extension/spline_maker/vertex_selection.py` | Component gestures, direct handle drags and selection markers |
| `extension/spline_maker/segment_selection.py` | Logical segments, screen-space sampling, picking and level controls |
| `extension/spline_maker/region_selection.py` | Individual-spline and Whole geometry selection |
| `extension/spline_maker/region_geometry.py` | Validated closed-interior geometry |
| `extension/spline_maker/edit_drag.py` | Move snapshots, axis/plane projection, update and rollback |
| `extension/spline_maker/tangent_drag.py` | Vertex tangent rotation/scaling |
| `extension/spline_maker/transform_gizmos.py` | Tool-owned axes, rings, pads and center controls |
| `extension/spline_maker/display.py` | Bright source-curve overlay and session display settings |
| `extension/spline_maker/ui.py` | Menus and visible controls |
| `tests/blender/` | Background registration, native-data, geometry and synthetic interaction checks |

The decisions below record the sequence of milestones; later refinements supersede earlier deferrals and mappings.

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

## SM-011 segment selection

`segment_selection.py` enumerates native Bézier segments by spline index and starting point, including cyclic closing segments and skipping hidden endpoints. It subdivides each world-space cubic with de Casteljau until projected control-polygon error is at most 0.75 pixels, capped at depth ten. Picking uses minimum screen-space distance to the resulting line edges within nine pixels. Unprojectable spans break the polyline rather than creating a phantom bridge. Equal-distance ties resolve in stable spline/start order; this is not occlusion-aware surface picking. The overlay draws selected segments blue and hovered segments mint.

Logical identity uses native outgoing/incoming handle selection flags paired with endpoint anchor flags. Selecting an edge sets its start's right flag and end's left flag; anchor selection is the union. Selecting separated segments therefore cannot imply the intervening segment merely because its endpoints are selected. Native Edit Mode undo stores these flags; the background suite verifies Undo/Redo of two different segment selections. No cached RNA segment references or custom source-curve metadata are required. In Segment level, direct handle drags preserve all selection flags, retaining identity.

Selection level is a transient WindowManager enum reset on unregister. Visible buttons and guarded 1/2 bindings expose Vertex and Segment. Level changes cancel active gestures; entering Segment clears selection, and returning to Vertex retains endpoint anchors while clearing edge-code handle flags. Level changes are UI context changes, not an additional undo step. The current level itself is not part of Curve Edit Mode undo. Region and whole-curve levels are deferred.

Move resolves the logical endpoint set and snapshots each point once. Vertex-mode math and direct handles remain available; segment Rotate/Scale gizmos and tangent steps are disabled because their selection-center semantics belong to SM-015. Background checks cover geometry, identity, native undo, lifecycle, and projection; actual mouse dispatch and rendered picking still require viewport acceptance.

The owner accepted segment highlighting, selection, Move, and returning to Vertex editing in 0.11.0, then confirmed the centered gizmo in 0.11.1. `move_origin` averages unique selected endpoints in Segment level; the Move operator uses the same origin for its projection plane. For a curved segment, this is its anchor midpoint rather than a point evaluated along the curve.

## SM-012 region and whole-curve selection

`region_geometry.py` validates native closed Bézier loops in a local plane derived from all anchors and handles. Planarity tolerance is max(1e-6, extent × 1e-5). Curves are sampled at extent × 0.0005 flatness, with a 2048-vertex safety cap. A sweep broad phase rejects self-intersections/touches, while coplanar boundary intersection/containment rejects overlaps, nesting and holes. This is a bounded polygon approximation, not an exact curve-boolean kernel. Invalid closed boundaries disable Region conservatively; open splines are excluded without blocking otherwise eligible loops. Hidden boundaries and degenerate/nonplanar curves have explicit reasons.

`region_selection.py` caches validation by copied source coordinates/topology/visibility and data identity, storing no RNA point references. Geometry changes invalidate the cache; unregister clears it. Interior picking intersects the mouse ray with each candidate plane, transformed with the inverse-transpose normal. Multiple projected hits are reported as ambiguous. Selection/hover draw only outlines. Region selection uses all native anchor and handle flags on each chosen loop, retaining native Edit Mode Undo/Redo without custom persistent metadata. Region Move resolves unique selected boundary anchors and uses their center.

Whole selection sets native flags for every point of every spline, including hidden points. Deselecting source geometry never deselects or changes the active object. The sidebar distinguishes those states and exposes Select/Clear actions. Direct handle gestures preserve composite selection flags. Whole Move is disabled to avoid baking an object transform into edit coordinates before SM-014; non-vertex Rotate/Scale remains deferred to SM-015.

The existing transient selection-level enum now has all four entries, with scoped 1–4 shortcuts and visible controls. Region's button is disabled with a reason when no valid loop exists; its shortcut reports the same reason. Entering Whole selects geometry; entering Segment/Region clears it; Vertex retains anchors. Drawing Finish selects the new source geometry and sets Whole level. These UI level changes remain separate from native source-selection undo. Background checks validate geometry, projection, selection and native Undo; viewport acceptance remains pending.

## 0.12.1 entry shortcuts and readable curve display

2/3 now bind an entry operator whose poll permits one supported Bézier object in Curve Edit Mode even with a native tool active. It activates Spline Maker Select when needed, then delegates to the existing selection-level operator. Normal level changes and 1/4 retain their existing scope. Object Mode and mesh contexts fail the entry poll. This makes entry explicit rather than changing native Q/W/E/R bindings outside Spline Maker.

`display.py` registers an earlier POST_PIXEL callback than the selection markers. It samples native Bézier source segments, paints unselected spans in a light-blue session color, and paints selected spans blue. The custom selection/hover callbacks draw afterward. This callback is independent of the active workspace tool in supported Curve Edit Mode, and respects Show Overlays/hidden points. It shares the existing screen-space sampling approach; no source material, geometry, or global theme is changed. Bright-overlay enabled/color properties live on WindowManager and are cleared on unregister. The panel also exposes Blender's `View3DOverlay.show_curve_normals`, verified against the installed 5.2.4 UI scripts and the [official API](https://docs.blender.org/api/current/bpy.types.View3DOverlay.html#bpy.types.View3DOverlay.show_curve_normals). That native viewport option is not automatically changed by registration.

Keyboard dispatch and rendered contrast/ordering still require viewport acceptance; background checks establish operator entry, merged maps, and lifecycle only.

## 0.12.2 explicit Edit Mode exit

`SPLINE_MAKER_OT_finish_edit` in `feasibility.py` provides the shared exit action. It cancels/rolls back owned move, tangent, and selection gestures, sets the Edit workspace tool to native Select Box, calls Blender's native Object Mode transition, then sets Object Mode Select Box and resets the transient level to Vertex. The active object and committed source geometry remain under Blender's normal mode-transition handling. Clearing the gizmo hit registry discards transient group references.

The panel button is available in supported Curve Edit Mode, including with native tools active. A separate guarded shortcut operator delegates to it only when a Spline Maker Edit tool is active. Curve and 3D View keymaps give Esc priority in that context, while existing modal operators consume Esc for cancellation first. Drawing remains in its own Object Mode modal scope. The native mode dropdown remains available as an exit in previous builds and unsupported edit contexts.

Background checks verify mode/tool transitions and data preservation. Physical Esc priority and panel rendering await viewport acceptance.


## 0.12.3 drawing lifecycle and native-compatible keys

Successful Finish switches the Object workspace tool to native Select Box after commit and modal cleanup. This covers open and closed finishes, preventing the next selection click from invoking the armed Draw tool. Existing curve geometry and initial Whole geometry selection are preserved.

The original 4/Whole shortcut is removed. Guarded 4 now shares the existing Object Mode exit with Esc. Whole curve remains a visible selection button. The owner explicitly requested this native-compatible workflow; 5/6 are left to the existing Blender keymap.

The display callback now samples unselected visible all-Bezier curve objects in Object Mode through their own transforms. Selected objects keep native outlines. Object Mode sampling includes hidden edit points; Edit Mode retains its prior hidden-point behavior. Display controls are exposed in both panel contexts. This remains a screen-space overlay with the existing depth/visibility limitations, not a source material or geometry change. Rendering and physical workflow acceptance remain pending.

## 0.12.4 explicit Edit entry

`spline_maker.enter_edit` in `feasibility.py` is shared by the Object Mode panel button and guarded 6 bindings in Object Mode, Curve, and 3D View keymaps. Object entry requires a single selected editable all-Bezier curve, uses the native mode transition, then delegates to the existing Q Select tool and Vertex-level operators. In supported Curve Edit Mode it also works from native tools or another component level. Repeated 6 stays in Edit Mode. Poll rejects mesh/other object contexts and Object Mode multi-selection; native 1/5 are unchanged. Unregister removes all owned bindings through the existing shortcut registry.

The owner accepted 0.12.3, explicitly confirming Object Mode color and 4 exit. The added 6 shortcut and button require their own physical viewport check.

## 0.12.5 individual spline selection

The existing internal `REGION` enum and `selected_regions`/`select_regions` helpers now represent the visible Spline level. Their eligible set is every fully visible Bezier spline, independent of closure or planarity. Native anchor/handle flags encode each complete selected path, so selection Undo/Redo and Move reuse the existing data paths. Level entry automatically selects index 0 only when the object actually contains one spline; multiple splines start empty. Repeated 3 reselects a sole path.

Boundary and anchor picking use projected source geometry and return spline identities before attempting closed-interior tests. Multiple hits report ambiguity. The existing cached planar-loop validation remains responsible only for safe interior picking. Boxes require all projected anchors and sampled curve edges of an individual spline to be enclosed. A spline containing hidden points is excluded from this level, preventing Move from affecting only part of a path. Whole-object geometry selection still includes all source splines. Attach and topology changes are not implemented here.

The owner confirms 6 entry works in 0.12.4. The Spline-level refinement requires separate viewport acceptance.

## SM-013 tool/level integration (0.13.0)

`enter_selection_level` now accepts all four existing levels. Visible panel buttons and 1/2/3 call this operator; its supported-curve poll permits a native Curve Edit tool, activates Q Select if needed, then delegates to the original level-change implementation. Object Mode and mesh editing still fail that poll. 1 is no longer dependent on the Spline Maker workspace tool being active. Panel level controls render for supported native Curve Edit contexts as well as active Spline Maker tools. Tool/gesture hints are limited to the active custom context.

`tests/blender/control_checks.py` exercises the shared entry path and every Q/W/E/R transition across Vertex, Segment, Spline and Whole with real transformed native curve data. The existing gizmo draw-preparation method is called with synthetic controls to verify visibility state and world-space placement, including Q hiding all controls. This does not verify GPU rendering or physical gizmo dispatch. Existing lifecycle and both-keymap priority checks remain in the full smoke suite.

The owner accepted 0.12.5's Spline selection workflow overall, then accepted SM-013 in 0.13.0, explicitly confirming Move in Vertex/Segment/Spline. This is overall task acceptance rather than an itemized report for every tool/keymap case. Whole curve Move remains the next SM-014 implementation task.

## SM-014 Whole curve Move (0.14.0)

The audit confirmed that the remaining implementation gap was `selected_anchors` returning an empty set for Whole level. It now returns every source Bezier anchor, including hidden points, when all source geometry is selected. The shared Move snapshot captures each point once and translates anchors and both handles by the world-axis/plane delta converted through the inverse object matrix. Existing gizmo centering, modal hiding, repeated-update behavior, cancellation and cleanup apply unchanged. Whole Rotate/Scale remains disabled.

An installed 5.2.4 LTS check changed object location between native Curve Edit undo pushes. Undo and Redo left the object at the changed location. Direct object-transform mutation in Curve Edit Mode therefore fails the required undo contract. Whole Move uses source geometry translation in Edit Mode; native Object Mode remains the object-transform path. The object matrix, origin and hierarchy stay unchanged. This supersedes the previous plan to implement Whole Move as an object transform while keeping Curve Edit Mode.

`whole_move_checks.py` covers multiple splines with Free/Aligned/Auto/Vector handles, hidden points, rotated/nonuniformly scaled parents and objects, all axes/planes, no compounded preview, selection/type preservation, no-op release, cancellation, tool-change/unregister rollback and native geometry Undo/Redo. The old test-curve sidebar button is removed; its operator remains internal for background fixtures. Viewport acceptance of Whole curve Move remains pending.

## 0.14.1 Segment crossing-box selection

`segment_selection.box` now clips each existing sampled screen-space edge against the inclusive selection rectangle and selects a logical segment if any edge intersects. The two-axis parameter-interval test includes endpoint, edge and corner touches, plus crossings with both sample endpoints outside. It rejects disjoint edges whose bounding boxes merely overlap, unlike a bounding-box-only test. The existing 0.75-pixel adaptive curve sampling, projection breaks, native selection flag encoding, hidden-point filtering and Shift-add behavior remain shared with click selection. Spline/Whole box logic stays separate and requires enclosure. The panel hint now describes touching a segment.

The owner accepted Whole curve Move in 0.14.0, completing SM-014. The Segment box correction requires its own viewport check.

## SM-015 selection-center Rotate/Scale (0.15.0)

The accepted 0.14.1 selection/Move version was committed and pushed as `5807157` before beginning this task. `tangent_drag.py` now resolves composite selection through `edit_drag.selected_anchors`, capturing each native point once by spline/point index. The same modal operator handles both existing vertex-tangent transforms and composite geometry transforms. A non-null local pivot selects the geometry path: anchors and both handles are transformed from the original snapshot about the average of selected anchors. The snapshot now restores anchors as well as handles/types. Vertex mode continues to transform tangents about their own anchors.

World rotation/axis-scale matrices are conjugated through the object's world matrix, accounting for rotation, nonuniform scale and parent transforms. Source geometry stays in native Curve Edit undo and the object matrix is unchanged, matching the SM-014 decision. Composite transforms retain handle types; native Auto/Vector tangent recalculation still applies. The existing step operator shares the same snapshot/math path. Composite steps use global Z rotation and uniform scale; the accepted Vertex step stays local Z.

The gizmo group no longer suppresses composite E/R controls, and hides every control during either Move or Rotate/Scale preview. Polls reject empty/unsupported selections. Edge-on rotation planes and view-aligned scale axes cancel safely with a reason. Orthographic ray origins now use the installed API's zero far-clip clamp and an analytic line/plane intersection; this avoids the precision loss found by the new axis-rotation checks while preserving shared Move/interior picking.

`transform_checks.py` covers centered math, shared endpoints, unselected geometry, parent transforms, hidden Whole points, all rotation/scale controls, noncompounding preview, cancellation, no-op/identity restoration, tool-change/unregister rollback, type preservation and native Undo/Redo for drags and step buttons. Physical gizmo dispatch, rendered preview, panel layout and actual undo grouping require the SM-015 viewport procedure.

## 0.15.1 Select entry and shortcut priority

The owner accepted the 0.15.0 transform workflow but reported native Select Box on re-entry and Q failing to activate Spline Maker. Object Mode 1 previously used Blender's native mode entry, and `tool_shortcut.poll` deliberately rejected Q in native Edit tools. A dedicated `select_shortcut` now permits the supported Curve Edit context and delegates to the same Select switch as the button; W/E/R retain their existing active-tool guard.

A separate Object-only `enter_vertex_edit` shortcut delegates to the existing `enter_edit` action. It binds 1 in Object Non-modal, Object Mode and 3D View, while 6 entry now also binds Object Non-modal. The Object-only poll lets existing Curve Edit 1 level selection continue unchanged. Native/unsupported contexts fail these polls. Tool activation specifies VIEW_3D explicitly and redraws every area region. All bindings remain in the existing unregister registry; there are no mode handlers or timers.

`entry_checks.py` resolves applicable operators from the real merged default/Industry Compatible maps, exercising repeated 1/6 entry after both native and Spline Maker exits, Q from native tools and custom W/E/R, preservation of geometry/level/selection, the panel draw path's pressed Q button, and unsupported/no-selection guards. This strengthens operator/keymap coverage without claiming physical event delivery or rendered-panel verification.

## 0.15.2 offset XY scale square

`transform_gizmos.py` adds a tool-owned native primitive PLANE gizmo with an offset in positive XY and a SCALE/XY operator target. It is visible in composite Scale levels only, sharing the selection center and live-preview hiding rules. The existing XYZ boxes and uniform center keep their mappings.

`tangent_drag.py` accepts XY and uses a screen-space projection of the world XY diagonal for its signed drag factor. A diagonal matrix `(factor, factor, 1)` is conjugated through the object's world matrix and applied to the original geometry snapshot. No scale is baked into the object's transform. Edge-on XY views cancel before modal entry. The scale factor and snapshot lifecycle reuse the existing operator.

Focused checks cover the real gizmo setup's operator routing and visibility using synthetic controls, XY preview math under parent/nonuniform transforms, stable Z, repeated updates, cancel and native Undo/Redo. They do not verify rendered size, placement or physical picking. The owner accepted the prior 0.15.1 entry fixes overall.

## Later geometry

Profile generation may use Geometry Nodes or a controlled mesh generator. Choose after testing planar corner joins and alignment. Do not assume a rectangular Curve to Mesh sweep alone preserves wall thickness at every corner. Source curve remains editable; generated geometry is derived output. Height and width stay unit-aware settings independent of path vertex edits.

## Reference documentation

- Blender extension format: https://docs.blender.org/manual/en/5.2/advanced/extensions/getting_started.html
- Extension build CLI: https://docs.blender.org/manual/en/5.2/advanced/command_line/extension_arguments.html
- Use Blender's version-matched Python API documentation during implementation.
