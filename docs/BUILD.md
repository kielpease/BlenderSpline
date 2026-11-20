# Build and test Spline Maker

Spline Maker targets Blender 5.2.4 LTS on Windows. The ZIP is for local testing. The manifest carries a license placeholder until the owner selects a license and updates the metadata for distribution.

## Build and validate

Run from the project folder in PowerShell. Set `$blender` to your installed executable.

```powershell
$blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
New-Item -ItemType Directory -Force dist | Out-Null
& $blender --command extension validate extension/spline_maker
& $blender --command extension build --source-dir extension/spline_maker --output-dir dist
& $blender --command extension validate dist/spline_maker-0.9.1.zip
```

Blender writes the ZIP to `dist/spline_maker-0.9.1.zip` using its [extension packaging commands](https://docs.blender.org/manual/en/5.2/advanced/command_line/extension_arguments.html).

## Background smoke test

Use the same PowerShell session. The test installs the ZIP into a fresh profile under `dist` and restores the previous environment setting afterward.

```powershell
$previousResources = $env:BLENDER_USER_RESOURCES
try {
    $testProfile = Join-Path (Resolve-Path dist) ([guid]::NewGuid().ToString())
    $env:BLENDER_USER_RESOURCES = (New-Item -ItemType Directory $testProfile).FullName
    & $blender --background --factory-startup --python-exit-code 1 --python tests/blender/smoke_registration.py -- dist/spline_maker-0.9.1.zip
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

1. Install the current ZIP through **Preferences → Get Extensions → Install from Disk**. Use a fresh scene. In **Object Mode**, open **N → Spline Maker**, click **Add Bézier Test Curve**, and press **Tab** to enter Edit Mode. Use Top view (**Numpad 7**). Frame the curve if needed and set **Curve Edit Mode Overlays → Handles → All** if unselected handles are hidden. Keep viewport gizmos enabled. In the Gizmos popover, turn off the separate **Object Gizmos** for Move, Rotate, and Scale to isolate the probe controls.
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
5. In the left toolbar (**T**), open the **Add Cube** flyout and choose **Draw Spline**. The first viewport click should place the first point. The **Spline Maker** sidebar also has a Draw Spline entry. Verify that the cursor restores after Finish or Cancel. With the toolbar tool still selected, the crosshair indicates that Draw Spline is ready again. Right-click in the viewport to switch to Select Box. When drawing from the toolbar, the first right-click should finish the curve and the second should switch tools.
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
