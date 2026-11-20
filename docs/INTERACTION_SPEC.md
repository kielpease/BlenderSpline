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

## Tools

Q Select hides transform gizmos; W Move; E Rotate; R Scale. Buttons expose the same actions. Bindings apply only in Spline Maker context. Selecting a tool does not immediately start a mouse transform.

Proposed transform semantics to validate against the owner's expectations:

- Vertex Move: translate anchor and both handles together.
- Vertex Rotate/Scale: rotate tangent directions / scale tangent lengths about each selected anchor. Anchor positions remain fixed by default.
- Handle editing: directly drag its diamond in the view plane without changing tools. The owning anchor stays fixed. Linked handles preserve alignment and the opposite local length; independent handles leave the opposite handle unchanged. A manual Smooth edit becomes linked Bézier, and a Corner tangent edit becomes independent. Move/Rotate/Scale gizmos and sidebar tangent steps operate on selected anchors; a handle-only selection does not activate them.
- Segment: transform union of selected segments' endpoint data; shared endpoints only once. Adjacent unselected segments may change shape because they share anchors.
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
