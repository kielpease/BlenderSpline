# Build and test Spline Maker

Spline Maker targets Blender 5.2.4 LTS on Windows. The ZIP is for local testing. The manifest carries a license placeholder until the owner selects a license and updates the metadata for distribution.

Current accepted build: **0.15.2**, including the XY square, Move/Rotate/Scale and Select entry fixes. The next task is SM-016; its home-session handoff is in `AGENTS.md` and its resume procedure is in `TEST_PLAN.md`. Earlier milestone procedures record historical tests; later workflow refinements supersede their old key mappings and feature deferrals.

## Build and validate

Run from the project folder in PowerShell. Set `$blender` to your installed executable.

```powershell
$blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
New-Item -ItemType Directory -Force dist | Out-Null
& $blender --command extension validate extension/spline_maker
& $blender --command extension build --source-dir extension/spline_maker --output-dir dist
& $blender --command extension validate dist/spline_maker-0.15.2.zip
```

Blender writes the ZIP to `dist/spline_maker-0.15.2.zip` using its [extension packaging commands](https://docs.blender.org/manual/en/5.2/advanced/command_line/extension_arguments.html).

## Stable local installer

Keep all versioned test builds in `dist/`. Use `stable/spline_maker-stable.zip` as the single installer for the owner-approved build. Its manifest identifies the version. Both folders are Git-ignored, so a fresh checkout needs a local build of the accepted version before populating `stable/`.

After the owner accepts a candidate, set `$candidate` to its exact ZIP in `dist/` and validate it before replacing the stable copy. The original versioned ZIP stays in `dist/`.

```powershell
$candidate = 'dist/spline_maker-0.15.2.zip'
& $blender --command extension validate $candidate
if ($LASTEXITCODE -ne 0) { throw 'Candidate validation failed' }
New-Item -ItemType Directory -Force stable | Out-Null
Copy-Item -LiteralPath $candidate -Destination 'stable/spline_maker-stable.zip' -Force
```

## Background smoke test

Use the same PowerShell session. The test installs the ZIP into a fresh profile under `dist` and restores the previous environment setting afterward.

```powershell
$previousResources = $env:BLENDER_USER_RESOURCES
try {
    $testProfile = Join-Path (Resolve-Path dist) ([guid]::NewGuid().ToString())
    $env:BLENDER_USER_RESOURCES = (New-Item -ItemType Directory $testProfile).FullName
    & $blender --background --factory-startup --python-exit-code 1 --python tests/blender/smoke_registration.py -- dist/spline_maker-0.15.2.zip
} finally {
    $env:BLENDER_USER_RESOURCES = $previousResources
}
```

The smoke test checks install, enable, disable, and re-enable, including menu callback count, registration cleanup, and the placeholder action's effect on scene objects. It also checks the four tool keymaps, scripted tool activation, and tangent edits on native Bézier data.

## SM-001 viewport check (0.1.0)

1. In **Edit → Preferences → Get Extensions**, open the top-right menu and choose **Install from Disk**. Select the ZIP and enable **Spline Maker** in **Add-ons** if needed.
2. In the 3D Viewport in Object Mode, open **Add → Curve** and confirm **Draw Spline** appears once. Click it and confirm Blender reports that spline drawing is still in development and adds no objects.
3. Press **N** over the viewport and open **Spline Maker**. Confirm the panel shows the development status and its **Draw Spline** button gives the same result.
4. Disable **Spline Maker** in **Preferences → Add-ons** and confirm both entry points disappear. Re-enable it and confirm each returns once.

## SM-002 viewport check

When updating, disable **Spline Maker** and restart Blender before installing the new ZIP. If Blender has already copied the new version and reported an already-registered class, restart and check the installed version in **Preferences → Add-ons**. If it shows the new version, enable that copy.

1. Install the current ZIP through **Preferences → Get Extensions → Install from Disk**. Use a fresh scene. Draw a short mixed straight/curved spline using **Add → Curve → Draw Spline**, finish, select it and press **6** to edit. The old Add Bezier Test Curve sidebar button was removed in 0.14.0. Use Top view (**Numpad 7**). Frame the curve if needed and set **Curve Edit Mode Overlays → Handles → All** if unselected handles are hidden. Keep viewport gizmos enabled. In the Gizmos popover, turn off the separate **Object Gizmos** for Move, Rotate, and Scale to isolate the custom controls.
2. In the **Spline Maker** sidebar, click **Q Select** to activate the probe. Over the viewport, click an anchor, then click a single handle. Check that native selection can distinguish them.
3. Select an anchor and press **W** over the viewport. Check that Spline Maker shows colored Move arrows and that dragging an axis moves the anchor and both handles together. Press **Q** and confirm the Move gizmo goes away. Check that orbit and zoom still work.
4. With an anchor selected, press **E**. A small blue button should appear above the anchor. Click it or use **Rotate Handles 15°** in the sidebar. Both handles should rotate around the stationary anchor. Press **R** and apply **Scale Handles ×1.25**. Both handles should extend without moving the anchor. Undo once and confirm the previous handle lengths return.
5. Select just one handle in **Q Select**. Repeat an **E** or **R** step and check that only the selected handle changes. Switch to Blender’s own **Select Box** tool in the toolbar and confirm Q/W/E/R return to their normal bindings.
6. With a Spline Maker tool active, disable the extension and confirm its toolbar tools, sidebar controls, and step button disappear. Re-enable it and check that each tool is present once.

## SM-003 viewport check

1. Install the current ZIP after disabling the old build and restarting Blender. Open a fresh scene in Object Mode. In **Top Orthographic** (Numpad 7), launch **Add → Curve → Draw Spline**. Check that the cursor becomes a crosshair before the first click. Click three different locations. Check for three blue point marks and a live preview line.
2. Press **Ctrl+Z** once and check that only the last point disappears and the scene's other objects stay unchanged. Repeat via **Backspace**. Orbit with the middle mouse button, pan with Shift+MMB, and zoom with the wheel. With Industry Compatible, test Alt+left mouse orbit, Alt+middle mouse pan, and Alt+right mouse zoom. After zooming, click another point and confirm the drawing session is still active. Place more points from the angled view, then return to Top view. The points should still lie on the original plane. In exact Front view, the original Top plane is edge-on and clicks should leave the point count unchanged.
3. Click **Finish** or right-click without modifiers with two or more points. Check that a single editable Bézier object appears and the preview disappears. Return to Object Mode if needed and press **Ctrl+Z** to remove the finished object in one step. Press **Ctrl+Shift+Z** to restore it.
4. Launch again from an angled **Perspective** viewport. Place several points, orbit, place another point, then click **Cancel**. Check that the preview disappears and the Outliner is unchanged. Repeat using **Esc**.
5. In the left toolbar (**T**), open the **Add Cube** flyout and choose **Draw Spline**. The first viewport click should place the first point. The **Spline Maker** sidebar also has a Draw Spline entry. Verify that the cursor restores after Finish or Cancel. Finishing now switches to Select Box automatically; choose Draw Spline again to create another curve. Right-click in the viewport to switch to Select Box. When drawing from the toolbar, right-click finishes the curve and returns to Select Box in one action.
6. On a finished Draw Spline curve, enter **Edit Mode**, choose **Q Select** in the Spline Maker sidebar, and select a corner. Check that **W** shows Move arrows and **E** and **R** show the tangent step button. Applying a tangent step makes the affected Vector handles Free. Check that the step changes the handles around the fixed anchor and that Undo restores the corner.

## SM-004 viewport check

1. In a fresh scene, move the 3D cursor to an offset such as **X 4, Y −2, Z 3** using the **View** sidebar's 3D Cursor controls.
2. Start separate Draw Spline sessions from **Top**, **Front**, and **Right** orthographic views. Place at least two points and finish each curve. Check that the object origin and all points are on the expected plane. Top keeps world Z at 3, Front keeps world Y at −2, and Right keeps world X at 4.
3. Start in an angled perspective view. Place two points, orbit, and place a third. Finish and verify that the curve still faces the starting view. In Edit Mode all points should have local Z equal to zero.
4. Start again in Top view, place a point, and switch to exact Front view while drawing. The probe should report that placement is unavailable. Return to Top view and confirm you can place the next point.

## SM-005 viewport check

1. Launch **Draw Spline** and move the pointer before clicking. A mint diamond should mark where the first vertex will land. After clicking, the vertex should turn blue and the mint line should follow the next preview. Moving over **Finish** or **Cancel** should hide the mint preview.
2. Place three corners. Try a second click at the last corner without moving, then move away and finish by right-clicking. The resulting open spline should contain exactly three vertices at the committed locations. Repeat with **Enter** or **Finish**.
3. Start another curve with a pre-existing object selected. Place two corners, then click **Cancel**. The Outliner, selection, and active object should match their pre-session state. Repeat with **Esc**.

## SM-006 viewport check

1. In **Top** view, choose **Draw Spline** and click two corners. Press and hold the left mouse button at the third point, drag diagonally, and release. The anchor should stay at the press location while the mint tangent guides extend symmetrically. The preview should bend while you drag.
2. Click a fourth corner and right-click to finish. Check that the first segment is straight and the segments next to the dragged point are curved. In Edit Mode, check that the clicked points have Vector handles and the dragged point has Aligned handles.
3. Repeat starting with a drag as the first point, including when launched via the toolbar Add flyout. Test a click with slight pointer movement and confirm it still creates a corner. Repeat from an angled view to check that the handles stay in the original drawing plane.
4. While drawing, place a dragged point, undo it, then add another and cancel. Check that no preview geometry or object remains.

## SM-007 viewport check

1. In Top view, place a first corner. Aim slightly away from horizontal, diagonal, or vertical. Hold and release **Shift** with the mouse still. The mint preview should snap to the nearest 45° direction and return to the pointer on release. Its distance from the previous vertex should stay the same.
2. Hold **Shift** while you click a corner. Repeat with a click-drag Bézier point. The anchor should snap on mouse press and stay fixed while the handles follow the drag. Release and re-press Shift during the drag to check that the anchor stays put.
3. Repeat from Front or Right view and from an angled perspective view. Orbit mid-draw and check that the snap directions still follow the original plane.
4. When you start from the toolbar, hold Shift on the first click. It should still place the first point under the pointer.

## Whole-spline Move viewport check

1. In a fresh scene with the 3D cursor at the grid origin, draw several vertices well away from the cursor. Include a click-drag Bézier point and finish.
2. Select the whole spline and activate Move. The gizmo should appear at the average position of the vertices. Drag an axis and confirm the entire spline moves together.

## SM-008 viewport check

1. Draw three corners and hover within about 10 pixels of the first one. The mint preview should connect to it and show **Click first point to close**. Click to close. In Edit Mode, verify the loop has three vertices.
2. Repeat with a click-drag first vertex. The closing segment should follow the first vertex's incoming handle. Try zooming before closing to check that the target remains easy to hit.
3. While drawing, use **Backspace** and **Ctrl+Z** to remove points. With only two points left, try closing. The session should remain active. Add a third point, close, then use **Ctrl+Z** and **Ctrl+Shift+Z** to remove and restore the entire loop.
4. Start a new drawing and hover over its first point with three points placed. Press **Esc** or click **Cancel** and check that no curve is created. Start again and use plain right-click to verify that it still finishes an open spline.

## SM-009 viewport check

1. Draw and finish a spline with at least one click-drag Bézier point. Enter Edit Mode and click **Q Select** in the **Spline Maker Edit** panel. With Industry Compatible, pressing Q from a native Blender tool enters Blender's Select Box. The Spline Maker **Handles** dropdown appears when Spline Maker Select is active. Set it to **All** to pick handles on unselected anchors, and leave **Show Overlays** on.
2. Hover over an anchor and then over a handle. Look for the mint square and diamond. Click a handle, Shift-click another component to add it, then Shift-click it again to remove it. Click empty space to clear the selection.
3. Drag a box around two anchors. Check that the anchors are selected. Shift-drag another box to add anchors. Press **Ctrl+Z** to undo the last selection, then press **W** to confirm the remaining selection carries over to Move.
4. Rotate and nonuniformly scale the spline in Object Mode. Return to Edit Mode, select **Q Select**, and repeat at two zoom levels. Check that orbit, pan, and zoom still work with your normal viewport shortcuts.

## SM-010 viewport check

1. Disable the previous build, restart Blender, and install `dist/spline_maker-0.15.2.zip` through **Preferences → Get Extensions → Install from Disk**. Draw a mixed straight/curved spline, finish, enter Edit Mode, and click **Q Select** in the Spline Maker sidebar.
2. Select one anchor, then right-click in the viewport. Choose **Corner**, **Smooth**, **Bézier**, and **Bézier Corner** in turn. Corner should straighten adjoining tangents; Smooth should calculate automatic tangents; Bézier should link tangent directions; Bézier Corner should permit independent tangents. The matching sidebar buttons should do the same thing. Anchor positions and vertex count must stay fixed.
3. Select only one handle and apply Bézier Corner. Both tangents of its owning vertex become Free, and the same handle remains selected. Use **W Move** to move that handle and verify the opposite handle stays fixed and the spline stays connected. Select the anchor and apply Bézier; moving one handle should now maintain tangent alignment.
4. Shift-select several anchors, change their type, and check that all selected vertices change together. Test **Ctrl+Z** and **Ctrl+Shift+Z** after each change and after a handle move. Confirm the prior types, shape, and selection return correctly.
5. Deselect everything; the menu actions and sidebar type buttons should be disabled. Switch to Blender's native Select Box tool and confirm right-click uses Blender's normal context menu. Return to Spline Maker, then disable/re-enable the extension and check for duplicate menus or bindings.

Right-click acts on the existing selection. Selecting a handle changes the type of both tangents at its owning vertex. Smooth and Corner recalculate tangent coordinates; Bézier may change directions while retaining lengths. Bézier Corner frees the existing tangents without splitting the curve. Multi-object editing and mixed Bézier/non-Bézier objects are unsupported for these controls.

## 0.10.1 tangent control regression check

1. Disable the previous version, restart Blender, and install the current ZIP. Draw a curve and select a vertex with Q Select. Click W Move; arrows should stay compact when zooming in and out.
2. Click E Rotate. Drag the blue ring around the selected anchor. Tangents should rotate continuously in the view plane while the anchor stays fixed. Release to finish; Ctrl+Z should restore the previous tangents and Ctrl+Shift+Z should reapply the drag.
3. Click R Scale. Drag the square-ended diagonal arrow away from/toward the anchor to lengthen/shorten tangents. Repeat with one handle selected, then several vertices. Each vertex retains its own pivot. The sidebar also exposes Drag Tangent actions and the earlier fixed-step buttons.
4. Repeat with Corner, Smooth, Bézier, and Bézier Corner vertices. A manual Smooth edit becomes linked Bézier; a Corner edit frees its tangents. On a linked single handle, rotation also rotates the opposite tangent; scaling retains the opposite length. Free tangents remain independent.
5. Start a drag, change the tangents, and press Esc or right-click. Coordinates and types must return exactly. Repeat on a rotated, nonuniformly scaled object and from an angled view. Confirm switching tools alone does not change geometry. Normal navigation is available between transforms; an active drag owns the pointer until finish/cancel.

These drag and visual-size checks have not yet been performed on 0.10.1.

## 0.10.2 tool switching regression check

1. Disable the old extension, restart Blender, and install `dist/spline_maker-0.15.2.zip`. With Industry Compatible, select a spline and use **1** or the viewport mode dropdown to enter Edit Mode. **Tab** is Menu Search in that keymap. Use **Ctrl+]** or the sidebar edge to show the sidebar, then open **Spline Maker** and click **Q Select** once.
2. Select an anchor or individual handle. With the pointer over the viewport, press **W**, **E**, **R**, **Q**. Check that the sidebar highlights the same mode, and arrows, rings, boxes, or no gizmo appear immediately without orbiting, panning, or zooming. Repeat using each sidebar button and in reverse order. Selection must remain unchanged.
3. Move uses red/green/blue Translate arrows. Rotate uses colored global-axis rings and a white outer view ring. Scale uses colored axis boxes and a white uniform center square. Dragging changes selected tangents around stationary anchors; Move remains native and moves selected anchors/handles. Edge-on axes can overlap or appear as lines in orthographic views; use an angled view to inspect all axes.
4. Verify individual-handle Move still works. On a Bézier Corner, move only one handle. On a linked Bézier, verify that the opposite tangent maintains alignment. Rotate/scale one handle, then several anchors; check each anchor stays fixed. Test Ctrl+Z/Ctrl+Shift+Z after a completed drag and Esc/right-click while dragging.
5. Click Blender's native Select Box or use **T** for Blender's Transform tool. Native shortcuts should return, and Spline Maker's sidebar should offer entry via Q Select. **T** is not a Spline Maker tool. Re-enter with the sidebar Q Select button before testing the scoped Q/W/E/R keys again.

The background checks pass on Blender 5.2.4 LTS. This live-rendering/drag procedure remains pending.

## 0.10.3 selection and direct handle test

1. Disable the previous build, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Select your spline, enter Edit Mode (1 with your Industry Compatible setup), open the Spline Maker sidebar, and click Q Select. Keep Show Overlays enabled.
2. In each of Q Select, W Move, E Rotate, and R Scale, start a left-drag in empty space and box several vertices. The vertices should select without changing tools. Shift-drag another box to add vertices. Clicking empty space should deselect. Check that pressing a gizmo still starts its transform instead of a marquee.
3. In W Move, select vertices and drag an axis arrow. The curve and selection preview should move; the gizmo should hide for the drag and return at the result on release. There should be no detached old arrow. Try Escape/right-click to cancel, Ctrl+Z to undo a committed move, and Ctrl+Shift+Z to redo it.
4. Drag the offset square between the X/Y arrows to move in global XY. From suitable views, test XZ and YZ squares. The center square moves freely in the view plane. An edge-on plane is unavailable; orbit to use it. Repeat with a rotated/nonuniformly scaled curve object.
5. In every Q/W/E/R tool, directly drag a small handle diamond. Its owning vertex must stay fixed; the active tool must remain unchanged. A drag beginning on a handle edits the handle instead of creating a box. Handle-only selection should leave vertex transform gizmos inactive.
6. Test a Bézier Corner: the opposite handle stays fixed. Test a Bézier: the opposite handle stays aligned and retains its length. Smooth becomes manually linked on editing; Corner handles become Free. Start a handle drag with another vertex selected, then press Escape: both geometry and the original selection must return. Test Ctrl+Z/Ctrl+Shift+Z after committing a handle drag.

The owner accepted this build's viewport workflow on 2026-11-20, reporting that everything worked wonderfully. This is overall acceptance; individual test cases were not separately logged.

## SM-011 segment selection test

1. Disable the previous version, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Draw a mixed straight/curved spline with at least five vertices. Enter Edit Mode (1 in your Industry Compatible setup), click Q Select, then click **2 Segment** in the sidebar. Scoped 1/2 keys work after entering a Spline Maker tool; Object Mode's native 1 binding remains available.
2. Hover near the middle of a curved segment. The curve itself should highlight mint; clicking should select it blue and mark its two endpoints. Repeat at several zoom levels and after rotating/nonuniformly scaling the object. The pick tolerance is nine screen pixels. Hidden endpoints exclude their segments.
3. Shift-click a second, separated segment. The intervening segment must remain unselected even when all its endpoints are selected. Shift-click a selected segment to remove it. Click empty space to clear selection. Box-drag around a whole segment to select it; Shift-box adds. Partial enclosure does not select a segment.
4. Select two adjacent segments and activate W Move. Move with an arrow, plane square, or center square. Their shared vertex must move once, with no doubled offset or duplicate point. Both selected highlights should persist. Cancel a move with Esc, then finish another and test Ctrl+Z/Ctrl+Shift+Z. Adjacent unselected segments may change shape because they share endpoints.
5. Undo/redo segment clicks and Shift toggles. Verify the exact segment highlights return. Change Q/W/E/R and verify segment identity survives. Segment Rotate/Scale should show a planned-feature explanation and no tangent-only gizmo; use W for segment transforms in this build.
6. Close another spline and pick its last-to-first segment. Try multiple splines in one curve object. In Segment, directly drag a handle diamond and confirm the segment selection stays intact. Switch to **1 Vertex** and verify selected segment endpoints remain selected. Re-entering Segment starts empty.

The owner accepted segment highlighting, selection, gizmo Move, and returning to Vertex editing in 0.11.0. Version 0.11.1 centers Move between the unique selected endpoints. Confirm the centered placement on one segment and a multi-segment selection, then test Move and cancel from an angled view. Region/whole-curve selection and segment Rotate/Scale remain outside SM-011.

## SM-012 whole curve and region test

1. Disable the previous version, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Draw and close a simple loop, including some curved segments. Finish, enter Edit Mode using your normal controls, and click Q Select. The panel should start at **Whole curve** with all source geometry selected. Choose **1 Vertex** for individual editing.
2. In Whole curve, click **Clear selection**. Geometry should deselect while the curve remains the active object. Click its boundary/interior or **Select all geometry** to select everything again. Test Shift-click, empty-space deselection, a box around the entire curve, and selection Undo/Redo. For multiple splines in one object, Whole selects all of them. Whole transforms are intentionally disabled; use Object Mode for native object transforms.
3. Click **3 Region**, then hover and click inside the loop. Only its boundary should highlight; there should be no generated mesh or filled region overlay. Shift-click another separate closed loop to add/remove it. A box selects a completely enclosed loop. Empty-space click clears selection. Check Undo/Redo, including which loop is selected.
4. With a region selected, use W Move. The gizmo should center on its boundary anchors and move the whole boundary. Cancel a drag, finish another, and test Undo/Redo. Direct handle diamonds remain draggable. E/R should explain that Rotate/Scale at this level is planned.
5. Test an open-only curve: Region should be disabled with an Open spline explanation; pressing 3 should report the reason. Test a self-crossing loop, a loop with an off-plane handle, touching/overlapping loops, and nested loops. They must report unsupported geometry instead of guessing a region. If one closed boundary is invalid, Region is conservatively unavailable for that object; fix it or separate the curve objects.
6. Repeat on a rotated/tilted/nonuniformly scaled object and at two zoom levels. Orbit an edge-on region to make its interior visible. Two otherwise valid loops at different depths may overlap on screen: an ambiguous click must preserve selection and request a different view.
7. Switch between all four levels and Q/W/E/R. Scoped 1–4 keys should agree with the sidebar. In the Industry Compatible keymap, 4 now means Whole curve inside an active Spline Maker Edit Mode tool; use the viewport mode dropdown to return to Object Mode. Native tools retain their normal keys.

SM-012 awaits viewport acceptance. Regions support simple planar loops with at least three vertices; holes, ambiguous overlaps, and complex/hidden boundaries are unsupported. Whole-curve transforms and non-vertex Rotate/Scale remain deferred.

## 0.12.1 keyboard and visibility check

1. Disable the old version, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Select a Bézier curve, use your normal **1** to enter Edit Mode, and leave Blender's native Select Box or Move tool active. Press **2** over the viewport without clicking sidebar Q first: Spline Maker should activate and enter Segment. Repeat from a native tool with **3** on a supported closed loop: it should enter Region. An open or unsupported loop must show its reason instead. Existing 1/4 bindings are unchanged.
2. In the **Spline Maker** sidebar, find **Curve display**, available even with a native Curve Edit tool active. Uncheck **Direction wings (normals)** to hide Blender's repeated arrow-like normals. This does not hide the Bézier editing handles.
3. Leave **Bright spline overlay** enabled and deselect geometry. The spline should be light blue rather than black. Use **Spline color** to choose a different unselected color. Selected/hovered parts retain their selection colors. Disable the bright overlay to return to native theme rendering.
4. Repeat at two zoom levels with native and Spline Maker tools. Turn Show Overlays off/on and confirm the additional coloring follows it. Test selected segments and regions to check that the base coloring does not obscure their highlights. Curve shape and scene objects must stay unchanged by these display controls.

Direct key delivery and actual rendered colors/normals await viewport confirmation. Overlay color and enabled state reset with the extension/session; the normals checkbox is Blender's native per-viewport setting.

## 0.12.2 Finish Editing test

1. Disable the previous version, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Enter Curve Edit Mode and activate a Spline Maker tool. In the sidebar, click **Finish Editing → Object Mode**. You should get the clean selected object outline, with no editing diamonds or tool gizmos. The same curve should remain active and retain its shape.
2. Re-enter editing, choose **Whole curve**, then Q Select. Press **Esc** over the viewport. It should return to Object Mode and native Select Box. Repeat from W/E/R and Vertex/Segment/Region levels. Whole curve selects source geometry within Edit Mode; it is not the mode-exit action.
3. Begin a Move, tangent, direct-handle, or box-selection drag and press Esc. The first Esc must cancel the gesture and restore its starting state while keeping Edit Mode. Press Esc again after cancellation: that press should return to Object Mode.
4. Re-enter Edit Mode using your normal controls. It should start with native Select Box; 2/3 can enter Spline Maker again. Verify geometry remains unchanged after repeated enter/exit cycles. Native tools and Object Mode should retain their normal Escape behavior.

Physical Esc dispatch and the panel button still need viewport acceptance. In earlier builds, choose **Object Mode** from the viewport's mode dropdown to leave Edit Mode without clicking the left toolbar.


## 0.12.3 drawing lifecycle, color, and mode keys

1. Disable the old build, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Start Draw Spline from the left toolbar, place three points, and click the first to close. Select Box should activate immediately. Click empty space or another object: no new spline should start. Repeat with an open spline finished using Enter, right-click, or Finish.
2. Enter editing using your native controls, including your reported 6/Edit binding. Test 1 Vertex, 2 Segment, and 3 Region on a supported loop. Press 4 to return to Object Mode and Select Box. Verify that editing, exiting and then selecting does not re-arm drawing. Esc and Finish Editing still work. Whole curve is now a sidebar button, not the 4 key.
3. Check your native 5 mode menu and 6/Edit behavior, and normal 1/2/3/4 behavior on a mesh primitive. The extension does not bind 5/6 or apply Curve-only entry/exit actions to meshes.
4. Deselect a spline in Object Mode: it should use the bright spline color. Select it: Blender's native selected outline should return. Test multiple unselected Bezier objects, hidden objects, and a curve with edit-hidden vertices. Object-hidden curves stay hidden; edit-hidden points still contribute to visible Object Mode geometry.
5. Change Bright spline overlay/Spline color from the Object Mode sidebar and verify the same setting while editing. Toggle the bright overlay and Show Overlays, and inspect curved spans at several zoom levels. Actual rendered color and screen-space depth behavior are part of this UI check.

The 0.12.3 workflow used 1/2/3 Vertex/Segment/Region, 4 Object Mode, and the owner's native 5/6 mode controls. This overrides earlier instructions in this document that assigned 4 to Whole curve. The owner accepted 0.12.3, explicitly confirming spline color and 4 exit. Version 0.12.4 adds the explicit 6 entry below.

## 0.12.4 Edit Spline entry

1. Disable the old extension, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Select a single Bezier spline in Object Mode. With the mouse over the viewport, press **6**: it should enter Edit Mode with Spline Maker **Q Select / Vertex** active, exposing the component editing controls without a sidebar Q click.
2. Press **4** to return to Object Mode, then **6** to re-enter. Repeat using the sidebar **6 Edit Spline** button. The curve shape and active object should stay the same, and no new curve should be drawn.
3. From Segment or Whole curve editing, press **6**: it should return to Q Select / Vertex while retaining selected anchors. Press 6 again: it should stay in Edit Mode.
4. Check meshes and other object types, an unselected active spline, and multiple selected objects: Spline Maker should not intercept 6. Confirm **1** and **5** retain their existing behavior.

The owner confirms pressing **6** works well. The sidebar button was not separately reported. Whole curve remains a visible component-selection button; **4** is Object Mode and **6** is the explicit spline-editing entry.

## 0.12.5 individual spline selection

1. Disable the previous extension, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Select a curve containing one spline and press **6**, then **3 Spline**. All its anchors and handles should select immediately. Test both an open path and a closed loop. Click empty space to deselect, then press 3 again to reselect the sole path.
2. Press **W**: Move should be centered on the selected spline's anchors and move the complete path. Cancel a drag, then complete one and check Undo/Redo. Return to **1 Vertex** and confirm its anchors remain selected for editing.
3. For a curve object already containing several Bezier splines, entering 3 should start with nothing selected. Click an open or closed path to select only it; Shift-click another to add/remove it. Box selection should enclose a complete path. The **Whole curve** button should select every source spline in that object.
4. Closed-loop interiors should remain selectable where validation is unambiguous. For crossed, nonplanar, nested, or overlapping loops, pick an unambiguous boundary instead; ambiguous hits should preserve selection. Unhide all vertices of a path before selecting it as a spline.

ZIP validation and the full background suite pass on Blender 5.2.4 LTS. The new physical 3 selection, drawing of highlights, mouse boxes and Move workflow await acceptance. Attach and Spline Rotate/Scale remain future work.

The owner subsequently accepted the 0.12.5 Spline selection refinement overall, reporting that it works well.

## SM-013 tool/level integration (0.13.0)

1. Disable the previous extension, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Select a Bezier curve and enter editing with **6**. Choose Blender's native Select Box or Move tool. The Spline Maker sidebar should still show **1 Vertex / 2 Segment / 3 Spline / Whole curve**.
2. From that native Edit tool, press **1** over the viewport. It should activate Spline Maker **Q Select / Vertex** without an extra Q click. Repeat from the native tool with **2**, **3**, and each selection-level button. A sole spline should still auto-select with 3. Object Mode's native 1 should retain its usual behavior.
3. Select vertices, then cycle **Q/W/E/R** using both keys and sidebar buttons. Repeat with selected segments, selected splines and Whole curve. Each tool change should retain the selected geometry and level. Q should immediately hide the gizmo; W should restore Move for Vertex/Segment/Spline, while E/R remain available for vertex tangents. Whole curve transforms and Segment/Spline Rotate/Scale remain visibly deferred.
4. In an existing Spline Maker tool, change levels using keys and buttons: the current tool should stay active. Return to native Select Box and confirm native Q/W/E/R behavior returns. Check that 4 exit and 6 entry still work and mesh shortcuts are unaffected.

ZIP validation and the full background suite pass on Blender 5.2.4 LTS. The suite checks selection/geometry preservation, entry, keymap priority and synthetic gizmo visibility state. Physical shortcut delivery, panel layout, immediate redraw and rendered gizmos remain for this viewport check.

The owner subsequently accepted SM-013 in 0.13.0, reporting Move works well in 1 Vertex, 2 Segment and 3 Spline. This is overall task acceptance rather than an itemized result for every case above. Whole curve Move remains for SM-014; Segment/Spline Rotate/Scale follows in SM-015.

## SM-014 Move cleanup (0.14.0)

1. Disable the previous extension, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Draw or select a Bezier curve and press **6** to edit. Quickly confirm the accepted **1 Vertex / 2 Segment / 3 Spline** Move workflow still behaves as expected.
2. Click **Whole curve**, then **W Move**. The gizmo should appear at the average of all source anchors. Drag an axis arrow, a plane square and the center square; every source spline should translate together. If the object contains more than one spline, confirm all of them move. Whole selection also includes edit-hidden points.
3. Start a Whole Move and cancel with **Esc** or right-click. Geometry should restore and editing should remain active. Commit a move, then check **Ctrl+Z** and Redo restore the complete geometry and selection. Click **Clear selection**: the gizmo should disappear; **Select all geometry** should restore it.
4. Test an object with rotation and nonuniform scale. A world X arrow should still move along world X. The object's origin/transform should stay fixed because this is a geometry edit. To move the object and its origin together, press **4**, then use native Object Mode Move.

The sidebar now omits the old test-curve button and explains that Whole Move translates all source splines. Whole and Segment/Spline Rotate/Scale remain future SM-015 work. ZIP validation and the full background suite pass on Blender 5.2.4 LTS; physical Whole gizmo dragging, rendered preview and operator undo grouping await this viewport check.

The owner subsequently confirms Move works as intended, accepting SM-014 overall.

## 0.14.1 Segment box selection

1. Disable the previous build, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Enter editing with **6**, then **2 Segment**. Drag from empty space to make a small box across only the middle of a long straight segment. The complete segment should select even though neither anchor is inside the box.
2. Repeat across the middle of a curved segment at two zoom levels, then reverse the box-drag direction. A boundary touch should count as a hit. A nearby box that does not touch the curve should leave it unselected; touching a shared anchor may select both adjoining segments.
3. Hold **Shift** while boxing part of another segment: it should add to the current selection. A plain box over empty space should clear selection. Check Undo/Redo and repeat with W active to confirm the tool stays active and the Move gizmo centers on the selected endpoints.

ZIP validation, focused intersection/projection checks and the full background suite pass on Blender 5.2.4 LTS. Physical drag selection and the updated panel hint await this viewport check. Spline/Whole boxes still require full enclosure.

The owner subsequently confirms the 0.14.1 correction works great and requests committing/pushing this accepted version.

## SM-015 centered Rotate/Scale (0.15.0)

The accepted 0.14.1 version was committed and pushed to `origin/main` as `5807157`. This 0.15.0 build is the next task for viewport testing.

1. Disable the previous extension, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Select a Bezier curve, press **6**, then **2 Segment**. Select part of a straight or curved segment with a box. Press **E**: rotation rings should appear at the midpoint of its anchors. Drag a ring; its anchors and handles should rotate together. Try the outer view-facing ring too.
2. Press **R** and drag an axis box, then the center box. Axis boxes scale on world X/Y/Z; the center scales uniformly. Use **Rotate Selection 15 degrees (Z)** and **Scale Selection x1.25** in the sidebar too. Switching tools alone should not change geometry.
3. Select two adjacent segments and repeat. Their shared anchor should move once. Neighboring unselected segments can reshape because they share endpoints. In **3 Spline**, select a complete path and rotate/scale it. If the object contains several splines, first select one path, then Shift-select more: they should transform about a common center. **Whole curve** transforms all source splines, including edit-hidden points.
4. Cancel a drag with **Esc** or right-click. It should restore the original geometry and stay in Edit Mode. Commit a drag, then test **Ctrl+Z** and Redo. Gizmos should hide during the preview and return at the committed/restored center. Q should still hide them.
5. Return to **1 Vertex** and use E/R. Anchors should stay in place while tangents rotate/scale about their own anchors. Direct handle diamonds should remain freely draggable. Geometry-level transforms should retain Corner/Smooth/Bezier/Bezier Corner types; native Auto/Vector tangents still follow their constraints.

ZIP validation and the full background suite pass on Blender 5.2.4 LTS, including centered transform math on parented/nonuniform objects, all axes, cancellation and native Undo/Redo data. Physical gizmo dispatch, redraw, visible controls and actual operator undo grouping await this viewport check. These Edit Mode transforms keep the object's transform and origin fixed. An edge-on ring or view-aligned axis reports unavailable movement; orbit or use the view/uniform control.

The owner subsequently confirms Move/Rotate/Scale work great for 1/2/3/4, accepting SM-015 overall. The Select entry correction follows below.

## 0.15.1 Q Select entry

1. Disable the previous version, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Draw and finish a spline, or select one Bezier curve in Object Mode. Press **1** over the viewport: it should enter Vertex editing with **Q Select visibly ON**, without a sidebar click. Press **4** to exit, then **6** to re-enter: Q should again be ON. Repeat both entry keys after a native mode-dropdown exit.
2. Choose Blender's native Select Box or Move tool while editing. Press **Q**: Spline Maker Q Select should activate, the sidebar button should show pressed, and its component controls should work. Repeat Q from Spline Maker W/E/R. Q should preserve the selected component level and geometry selection.
3. In an active Spline Maker W tool, change from Segment/Spline to **1 Vertex**: it should retain W, as before. **6** is the explicit reset to Q Select / Vertex. Meshes and unsupported contexts should retain native 1/6/Q; native W/E/R should remain available when a native Curve Edit tool is active.

ZIP validation and the complete background suite pass on Blender 5.2.4 LTS. New checks use real merged default/Industry Compatible maps and verify repeated entry, selection/geometry preservation, Q button draw state and binding cleanup. Physical key priority and the visible pressed state still require this viewport check.

The owner subsequently confirms the previously mentioned fixes work well, accepting 0.15.1 overall.

## 0.15.2 XY scale square

1. Disable the previous build, restart Blender, and install `dist/spline_maker-0.15.2.zip`. Enter editing, choose **2 Segment**, select a segment, and press **R**. Start in Top view so the world XY plane faces the view. A blue square should sit diagonally between the X and Y controls, offset from the white center box.
2. Drag the offset square outward/inward along its diagonal. World X and Y should grow/shrink together around the existing selection center, while Z stays fixed. The white center remains uniform XYZ scale. Test the control with a curved segment too.
3. Cancel a drag with Esc/right-click, then commit one and test Ctrl+Z/Redo. The square should hide during preview and return afterward. Check its size, separation from the center and ease of clicking at two zoom levels.
4. The square is also available in **3 Spline** and **Whole curve**. It should stay hidden in Vertex mode and Q/W/E. Orbit to an angled view and retry; an edge-on XY plane should report that the control is unavailable.

ZIP validation, focused control/transform checks and the complete background suite pass on Blender 5.2.4 LTS. Actual gizmo rendering, picking and drag feel remain for this viewport check.

The owner subsequently confirms the 0.15.2 control works great and requests commit/push for continuing at home. This is overall viewport acceptance, not a separate per-case report.

## 0.15.3 edit controls viewport check

1. Install `dist/spline_maker-0.15.3.zip`. Press **6** to enter editing. Check that **1 Vertex / 2 Segment / 3 Spline / 4 All** are at the top of the panel.
2. Select two separated vertices and press **W**. The gizmo should sit between them. Drag to move both vertices and their handles.
3. Press **E** and choose **Group** from the Rotate dropdown. Drag an axis ring or the outer view ring. The selected anchors and handles should rotate together about their average. Undo, choose **Tangents**, and verify an equivalent drag rotates the handles about their own anchors.
4. Press **4** to select all source splines in Edit Mode, then **Enter** to return to Object Mode. Check the same with **Numpad Enter** and the **Finish Editing** button.

## 0.15.4 edit snapping viewport check

1. Install `dist/spline_maker-0.15.4.zip` and enter Vertex editing on a spline with separated vertices. In Top view, select one vertex, press **W**, and drag the X arrow until its X coordinate is close to another vertex's. Hold and release **Shift** without moving the pointer. Repeat with the Y arrow or the XY pad.
2. With a handle visible, drag its diamond near the straight line between its anchor and the next vertex on that side. Hold Shift to snap onto the line and release Shift to return to free movement. Try a curved segment and an outer handle at an open endpoint.
3. Press **Esc** during an active drag to revert that preview. Press Esc again while idle to return to Object Mode and verify earlier completed edits are still present.

## 0.15.5 compact controls and transform readouts

1. Disable the previous build, restart Blender, and install `dist/spline_maker-0.15.5.zip`. Check that **Splines** appears in Add-ons and in the 3D Viewport sidebar.
2. Enter Edit Mode and hover across the icon row. The tooltips should read **Select (Q)**, **Move (W)**, **Rotate (E)**, and **Scale (R)**. Open **Info** at the bottom to view Shift hints.
3. Drag a rotation ring while holding **Shift**. Check 10° steps, exact 45° and 90° stops, and the angle callout near the pivot. Release Shift mid-drag to resume free rotation.
4. Drag a scale control while holding **Shift**. Check that the callout steps through whole percentages, with **100%** at the starting size. Try the XY and uniform controls and check that Esc clears the callout and restores the original geometry.

## 0.15.6 rotation, coordinates, and handle snapping

1. Install `dist/spline_maker-0.15.6.zip`. Select a vertex or segment and drag a rotation ring with **E** active. The rings should stay at the pivot and the angle should appear to their side.
2. Under **World position**, click **Y**, enter a new value, and confirm. The selected geometry should move along world Y until the displayed coordinate matches the input. Repeat with a segment or **4 All** and check Undo.
3. Drag a handle near the anchor's local horizontal or vertical line and hold **Shift**. Repeat near an adjoining segment line. The handle should snap to the nearest eligible line and return to free movement when Shift is released.

## 0.15.7 Scale and first-point grid snap

1. Install `dist/spline_maker-0.15.7.zip`. Press **R** and drag a Scale control. Confirm the widgets and the side percentage stay visible. Check the center, the axis controls, and the offset XY square in a composite level.
2. Start Draw Spline in Top view with the 3D cursor offset from a grid intersection. Hold **Shift** before placing the first point. The mint preview and committed vertex should align to the grid at the original drawing depth. Zoom in and repeat.
3. Place another point while holding Shift and check that the 45° direction constraint takes over.

## 0.15.8 Bézier handles on close

1. Install `dist/spline_maker-0.15.8.zip`. Place three corners, then press on the first point and drag away. Observe the tangent guides and curves on both sides of the seam.
2. Release to close. In Edit Mode, check that there are three vertices and that the original first vertex has two aligned handles. Repeat with a plain click to confirm the first vertex keeps its original type.
3. Press Esc mid-drag in a separate drawing and check the preview clears without creating an object.

## 0.16.0 interaction integration viewport check

1. Disable the previous build, restart Blender, and install `dist/spline_maker-0.16.0.zip`.
2. Select a Bézier curve and press **6**, then **4 All** and **W**. Begin a Move drag. Keep the primary button down and try wheel zoom and **Alt+middle-mouse** pan with Industry Compatible. In Blender's default keymap, try **middle-mouse** orbit. Release the navigation button, then continue dragging. The geometry should hold its current position while you navigate and resume from there.
3. Release the drag and undo once. Check that the curve returns to its original position in Edit Mode. Redo should restore the completed move. Repeat with Rotate, Scale, and a Bézier handle.
4. During a Scale drag, try **Alt+right-mouse** zoom in Industry Compatible, then plain right-click to cancel the drag. After canceling, right-click again to open the vertex menu. Try **Esc** on a separate drag, then press it again to exit Edit Mode.
5. Zoom while dragging a selection box. Try the axis and plane controls on a rotated or scaled curve. Switch to native Select Box, then press **Q** and check that your selection carries over.
