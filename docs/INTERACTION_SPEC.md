# Interaction specification

## Product contract

Primary target: Blender 5.2.4 LTS, Windows. The owner uses 3ds Max and values contextual menus, gizmos, and direct manipulation. This is original Blender tooling inspired by that interaction, not a claim of full Max compatibility.

## Drawing

Required entry: Add → Curve → Draw Spline. Desired additional entry: existing toolbar Add flyout. Blender integration for that specific flyout must be investigated rather than assumed.

Capture a drawing plane facing the initial viewport, passing through the 3D cursor. Top/bottom use XY, front/back XZ, left/right YZ; angled views use their view orientation. Plane local X/Y follow screen right/up at invocation. Store the curve in local coordinates so ordinary object transforms remain possible.

All placement occurs on this fixed plane. Orbit/pan/zoom remain available; orbiting never rotates the plane. If a view ray becomes nearly parallel to the plane, indicate unavailable placement instead of producing extreme coordinates.

Click places a corner. Click-drag creates Bézier handles without Alt. Use a small pixel drag threshold to distinguish clicks. Shift snaps the next segment direction to the nearest multiple of 45 degrees relative to plane axes, anchored at the last committed vertex. Constraint uses plane coordinates, not perspective screen angles. Initial proposal: retain projected radial distance, and constrain anchor placement independently from handle dragging.

Click first vertex closes a path with at least three vertices. No repeated endpoint is created. Provide Finish and Cancel controls. Proposed keys: Enter finishes; Escape cancels the current creation session; Backspace removes the last point. Right-click during drawing finishes an open spline; right-click during editing opens context menu. Preview geometry is never left behind as committed points.

## Selection levels

| Level | Meaning |
| --- | --- |
| 1 Vertex | Pick anchors and individual tangent handles |
| 2 Segment | Select logical curve segments and their affected endpoint data |
| 3 Region | Select boundary of a simple planar closed loop; not generated mesh faces |
| 4 Whole curve | All spline geometry in the active curve object |

Start at level 4 after finishing creation. An object may eventually contain multiple splines; level 4 initially means all splines in that object. Closed regions initially exclude holes, self-intersections, and ambiguous overlaps. Show a clear disabled reason when level 3 is unavailable. Region visualization must not accidentally fill a future wall's interior.

Selection should remain visually clear in Q mode. Shift-click toggles membership; empty-space click deselects; box selection supports vertices first. Preserve component selections when switching transform tools. Define and test how selection converts across levels rather than silently selecting unrelated components.

Owner refinement for 0.10.3: left-drag in empty space box-selects vertices in all four Spline Maker tools, preserving the active tool. Shift-drag adds vertices. A drag beginning on a visible handle diamond directly moves that handle, taking precedence over a selection box. Handle diamonds and guides remain available in each tool while viewport overlays are enabled. A drag beginning on a highlighted gizmo belongs to the gizmo.

SM-011 adds visible Vertex/Segment controls and scoped 1/2 keys while a Spline Maker Edit Mode tool is active. Entering Segment starts with an empty selection; returning to Vertex retains selected endpoints. Clicking a segment selects it, Shift-click toggles it, and empty-space click deselects. Per the 0.14.1 owner correction, Segment boxes select each segment whose projected curve touches or crosses the box; Shift-box adds. Vertex-level boxes retain their existing behavior. Direct handle dragging works in either level and preserves segment identity in Segment. Selected segments remain selected when switching Q/W/E/R; W translates their unique endpoint union. Segment Rotate/Scale is disabled with a visible reason until SM-015 supplies the specified geometry/pivot behavior. Keys 3/4 remain outside this issue.

SM-012 adds Region (3) and Whole curve (4). Region requires a simple planar closed loop with at least three vertices and no hidden points. Click its interior or boundary; Shift-click toggles loops, and boxes select fully enclosed loops. Highlight boundaries only. Open splines are excluded. An invalid closed boundary disables Region conservatively for the object; coplanar intersecting/touching/nested loops are rejected. Multiple eligible regions under the pointer are ambiguous: preserve selection and report a reason rather than choosing by depth. Noncoplanar loops can be selected separately when their projections are unambiguous.

Whole curve selects all source geometry in the active object, including all splines and hidden points; it does not change which object is active. Entering Whole selects all geometry. Clicking a curve or supported closed interior selects all; empty-space click or Clear selection deselects geometry while leaving the object active. Shift-click toggles, and a box must enclose all visible geometry. Select all geometry and Clear selection buttons expose explicit actions. A finished drawing starts at Whole curve level. In a Spline Maker Edit Mode tool, 1–4 mean component levels; use the viewport mode dropdown to leave Edit Mode, or a native tool to return to its keymap.

Direct handle dragging remains available and preserves Region/Whole selection flags. Region Move translates selected valid boundaries about their unique-anchor center. Whole-curve transforms remain disabled until object-transform integration; use Blender Object Mode for native object transforms. Region and whole-curve Rotate/Scale remain deferred. Returning to Vertex retains selected anchors. Entering Segment or Region starts empty. The selection level is transient UI state, separate from native selection Undo/Redo.

Owner refinement for 0.12.1: 2/3 are explicit Spline Maker entry shortcuts in single-object, all-Bézier Curve Edit Mode. They activate Q Select when a native tool is active, then enter Segment/Region. An unsupported Region reports its reason with the panel available. They do not enter Edit Mode from Object Mode or override mesh editing. Existing 1/4 behavior is unchanged. The Edit panel exposes Direction wings (normals), using Blender's viewport normals setting, plus a bright spline overlay and color picker. The overlay also works before entering a Spline Maker tool, respects Show Overlays and hidden points, and does not change source geometry or the global theme. Overlay color/enabled state is session UI state.

Owner refinement for 0.12.2: Whole curve remains a geometry-selection level within Edit Mode. Finish Editing → Object Mode is a visible exit action in the Edit panel. Esc invokes the same exit while a Spline Maker Edit tool is active and no modal gesture is consuming the event. During drawing or a drag, Esc first cancels that operation; a subsequent Esc exits editing if applicable. Exit preserves committed geometry and the active curve, returns to native Select Box in Object Mode, resets the stored Edit tool to native Select Box, and clears the temporary selection level to Vertex. Esc is not overridden in native tools or Object Mode. Re-entry can use the native mode controls and the existing 2/3 entry shortcuts.

## Tools

Q Select hides transform gizmos; W Move; E Rotate; R Scale. Buttons expose the same actions. Bindings apply only in Spline Maker context. Selecting a tool does not immediately start a mouse transform.

Proposed transform semantics to validate against the owner's expectations:

- Vertex Move: translate anchor and both handles together.
- Vertex Rotate/Scale: rotate tangent directions / scale tangent lengths about each selected anchor. Anchor positions remain fixed by default.
- Handle editing: directly drag its diamond in the view plane without changing tools. The owning anchor stays fixed. Linked handles preserve alignment and the opposite local length; independent handles leave the opposite handle unchanged. A manual Smooth edit becomes linked Bézier, and a Corner tangent edit becomes independent. Move/Rotate/Scale gizmos and sidebar tangent steps operate on selected anchors; a handle-only selection does not activate them.
- Segment: transform union of selected segments' endpoint data; shared endpoints only once. Adjacent unselected segments may change shape because they share anchors.
- Segment Move gizmo: use the average of the unique selected endpoints as its center. A single segment uses the midpoint between its anchors; this is a selection center, not an arc-length midpoint on a curved segment. The Move projection plane uses the same center as the displayed gizmo.
- Region: transform the full boundary as one unit about selection center.
- Whole curve: use object transforms where possible; do not bake transforms into control points unnecessarily.

A later pivot option can add selection-center versus individual-anchor behavior. Do not quietly change default behavior during implementation.

Move offers global XYZ arrows, XY/XZ/YZ plane squares, and a center square for view-plane translation. During Move, the live curve/selection preview replaces the gizmo; the gizmo returns at the committed or restored selection after finish/cancel. An edge-on plane or view-aligned depth axis reports unavailable movement rather than jumping. A completed drag forms one undo step; Escape or right-click restores the drag's starting geometry. Canceling a direct-handle gesture also restores its previous component selection.

## Vertex context menu

| Label | Intended behavior |
| --- | --- |
| Corner | Straight/vector tangents at the vertex |
| Smooth | Automatic tangent behavior |
| Bézier | Manually editable, direction-linked tangents |
| Bézier Corner | Independently editable tangents |

Blender's Vector/Auto/Aligned/Free handle types are an initial mapping, not proof of identical Max behavior. Preserve sensible handle lengths on conversion and test adjoining segment shapes. Tangent independence must never split the spline. A future topology Break command is separate.

## Explicitly deferred

Height/width geometry, insert/delete operations, attach/detach, weld, topology break, fillet/chamfer, outline, spline booleans, surface snapping, and arbitrary 3D path drawing.

## Decisions for hands-on validation

1. Vertex rotation/scaling defaults and multi-vertex pivot behavior.
2. Finish/cancel behavior while drawing and exact undo grouping.
3. Handle drag direction and linked-handle response.
4. Desired placement depth if 3D-cursor plane proves inconvenient.
5. Multi-spline whole-curve selection semantics.

These proposed defaults allow implementation to begin; they are not unresolved blockers for M0.

## Owner workflow refinement: 0.12.3

This refinement supersedes the original keyboard 4/Whole mapping: 1/2/3 select Vertex/Segment/Region; 4 invokes Object Mode exit in Spline Maker Edit tools. Whole curve remains a sidebar selection button. The owner's reported native 5 mode menu and 6/Edit controls are preserved; neither key is bound by the extension. Mesh editing retains its native workflow.

Every successful open or closed drawing Finish returns to native Select Box after committing the curve and removing the modal preview/cursor. Starting another drawing requires choosing Draw Spline again. This removes the armed Draw toolbar state after completion.

The bright spline overlay also colors unselected visible all-Bezier curve objects in Object Mode. Selected objects retain Blender's native selected outline. Object Mode sampling includes edit-hidden control points, because those points still contribute to the visible object. Object-hidden curves remain hidden. The same session color controls are available in Object and Edit panels. Show Overlays and the bright-overlay toggle control the added coloring; source geometry, materials and the global theme are unchanged.

## Owner workflow refinement: 0.12.4

6 now explicitly enters Spline Maker Q Select / Vertex editing from Object Mode when one editable all-Bezier curve is selected. The Object Mode panel exposes the same action as 6 Edit Spline. In supported single-curve Edit Mode, 6 activates Q Select and returns to Vertex level, retaining selected anchors. It does not toggle back to Object Mode: use 4 or Finish Editing to exit. This supersedes the prior decision to leave 6 unbound. 1 retains its existing behavior; 5, meshes, other object types, unsupported curves, and multi-object selections keep native controls.

## Owner workflow refinement: 0.12.5

3 is now Spline selection, superseding the closed-Region-only semantics above. If the active curve contains exactly one fully visible Bezier spline, pressing 3 or its sidebar button selects all of that spline's anchors and handles, even for open, nonplanar, or self-intersecting paths. Repeating 3 reselects a sole path after deselection. If multiple splines exist, entering 3 starts empty and clicking a path selects only that spline; Shift-click toggles paths and boxes select fully enclosed paths. It does not select other curve objects. Partially hidden splines are excluded to avoid incomplete transforms; unhide their vertices first.

Boundary/anchor picking identifies individual splines independently of region validation. Validated, unambiguous closed-loop interiors remain an additional way to pick; overlapping/nested/invalid interiors are not guessed. Boundary hits take priority over interiors; multiple boundary hits or overlapping valid interiors preserve selection and report ambiguity. Whole curve remains a separate button selecting all source splines, including hidden points. Returning to Vertex retains selected anchors. Spline Move uses the unique selected anchors' center; Spline Rotate/Scale and Attach remain deferred. No topology is changed by selection.

## SM-013 integration: 0.13.0

1 now joins 2/3 as an explicit selection-level entry from a native tool in supported single-object Bezier Curve Edit Mode. All four visible selection-level buttons remain available there before Q activation and call the same entry action. Entry from a native tool activates Q Select and then chooses the requested level. Changing levels from an existing Spline Maker tool preserves that tool. Object Mode's native 1 is unchanged; 6 remains the explicit spline-editing entry, and 4 remains the scoped Object Mode exit.

Tool-only changes through Q/W/E/R or their buttons preserve the selection level, component flags, and geometry. Q hides all transform controls. Level changes retain the established rules: Segment clears on entry, Spline auto-selects a sole path or clears on multi-path entry, Whole selects all source geometry, and Vertex retains anchors while clearing composite handle codes. Whole Move and non-vertex Rotate/Scale remain disabled until their respective transform tasks.

## SM-014 Move completion: 0.14.0

Whole curve plus W now moves every source spline in the active curve object together, including edit-hidden points. The gizmo uses the average of all source anchors. Clearing Whole selection removes the gizmo until the complete geometry is selected again. XYZ arrows, XY/XZ/YZ pads and the view-plane center share the existing Move behavior, with one snapshot per unique anchor, both handles following, cancel rollback and one completed operator undo boundary.

This supersedes the previous Whole Move deferral. In Edit Mode, Whole Move translates source geometry through the object's inverse world matrix; the object's transform, origin, parent and children remain unchanged. A check on installed Blender 5.2.4 LTS showed that native Curve Edit Undo does not restore direct object-location changes. Geometry translation therefore keeps this edit action in native curve undo. To translate the object and its origin together, use 4 and native Object Mode Move. Whole Rotate/Scale and Segment/Spline Rotate/Scale remain SM-015 work.

## Owner Segment box correction: 0.14.1

At level 2, a box selects a segment if any part of its projected curve touches or crosses the box. Neither anchor needs to be inside. Rectangle direction does not change this rule. A touch at a shared anchor selects each incident segment that touches the box. Shift-box adds touched segments to the existing selection; a plain box replaces it, and a plain box over empty space clears it. Hidden/unprojectable segments remain excluded. This replaces the earlier full-enclosure rule for Segment only; Spline and Whole boxes retain their enclosure behavior.
