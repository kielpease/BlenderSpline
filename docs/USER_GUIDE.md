# Splines user guide

Splines 0.18.0 is verified on Blender 5.2.4 LTS for Windows. The ZIP installs as **Splines** and uses the extension ID `spline_maker`.

## Install or update

Build `dist/spline_maker-0.18.0.zip` from the repository or use the local stable installer if it is available. Both paths contain an installable ZIP. [Build instructions](BUILD.md#build-and-validate)

In Blender, open **Edit → Preferences → Get Extensions**. From the top-right menu, choose **Install from Disk** and select the ZIP. Enable **Splines** under **Add-ons** if needed. When replacing a previous build, disable it and restart Blender before installing. If Blender reports an already-registered class, restart and check the version under **Add-ons** before enabling it again.

## Draw an outline

1. In Object Mode, orient the viewport and put the 3D cursor at the desired drawing depth. Choose **Add → Curve → Draw Spline**, or press **N** and use **Draw Spline** in the **Splines** sidebar tab. The starting view fixes the drawing plane for that spline.
2. Click for a corner or click-drag to make a vertex with linked tangent handles. Hold **Shift** on the first point to snap to the drawing-plane grid. Hold it on later points for 45° direction steps.
3. Press **Backspace** or **Ctrl+Z** to remove the last preview point. Right-click or press **Enter** after at least two vertices to finish an open spline. To close a spline with three or more vertices, click its first point. Click-drag from that first point to set linked handles at the seam.
4. Press **Esc** or click **Cancel** to discard the drawing. Once the spline is finished, Blender Undo removes the created curve object in one step.

You can orbit, pan, or zoom during drawing. Click placement works best when you can see the drawing plane. In an edge-on view, rotate the viewport back toward that plane before placing another point.

## Select and edit

Select a single editable Bézier curve in Object Mode and press **6** or **1**, or use **Edit Spline** in the **Splines** sidebar. **6** enters Vertex mode with **Q Select** active. In Curve Edit Mode, **Q** also enters Splines Select from a native tool. The level buttons and tool icons in **Edit Splines** provide the same actions.

| Key | Level | Behavior |
| --- | --- | --- |
| **1** | Vertex | Select individual anchors and handles. |
| **2** | Segment | Select spans between anchors. Box selection includes any segment the box touches. |
| **3** | Spline | Select an individual open or closed spline. A single-spline object selects its spline automatically when all vertices are visible. A box must enclose the spline. |
| **4** | All | Select all source splines in the active curve object, including hidden points. |

Use **Shift-click** to toggle selection or **Shift-drag** a selection box to add to the selection. Small squares mark anchors and diamonds mark handles. Drag a handle's diamond directly in any Splines edit tool. Right-click while idle to choose **Corner** (straight tangents), **Smooth** (automatic tangents), **Bézier** (linked manual tangents), or **Bézier Corner** (independent tangents).

| Key | Tool | Behavior |
| --- | --- | --- |
| **Q** | Select | Pick components and hide transform gizmos. |
| **W** | Move | Drag a world axis, a plane square, or the view-plane center. |
| **E** | Rotate | Drag an axis ring or the view-facing ring. In Vertex mode choose **Tangents** or **Group** in the sidebar. |
| **R** | Scale | Drag an axis box or the uniform center. At levels 2–4, the offset XY box scales world X and Y together with Z fixed. |

Segment, Spline, and All transforms pivot around the average of the unique selected anchors. Vertex Move also uses the selected anchors' average. Vertex Rotate in **Tangents** mode and Vertex Scale work around each anchor. **Group** rotation rotates the selected anchors and their handles together.

Hold **Shift** while rotating to snap in 10° steps with additional 45° stops. Hold it while scaling for 1% steps. For a single vertex Move, Shift can align with a nearby vertex along the eligible world X or Y direction. For a direct handle drag, Shift can align to the spline's X/Y directions or the adjoining segment line. Expand **Info** in the sidebar for the relevant hints. To set an exact position, select geometry and click an axis under **World position**.

With Industry Compatible, you can hold a gizmo drag and use the wheel to zoom or **Alt+middle-mouse** to pan. In the Default keymap, **middle-mouse** orbit was checked during Move. The preview holds its current shape while you navigate. Release the drag to commit it. **Esc** or an unmodified right-click cancels the active gesture. **Enter**, or **Esc** when idle, finishes editing and returns to Object Mode.

## Save and reopen

Save the `.blend` normally. Committed anchors, handles, and closure are native Blender curve data. Saving cancels a pending preview. On reopen, Splines session controls return to their defaults and an open viewport using a Splines tool switches to native Select Box. Select the curve and press **6** to resume.

## Known limits

- Custom editing supports one editable all-Bézier curve object at a time. Use Blender's native tools for other curve types or multi-object editing.
- If a world axis faces the viewport or an active plane is edge-on, orbit to make the control usable.
- If a spline is partially hidden, unhide its vertices before using **3 Spline**. For overlapping or ambiguous closed interiors, pick a visible boundary.
- Custom topology operations such as insert/delete, attach/detach, and weld are planned. The **Bézier Corner** command changes tangents while keeping the spline connected. Profile and wall geometry are also planned.
- Compatibility outside Blender 5.2.4 LTS on Windows is unverified. The test plan lists the exercised keymaps and viewport cases. [Test results](TEST_PLAN.md#sm-018-package-and-user-guide)
