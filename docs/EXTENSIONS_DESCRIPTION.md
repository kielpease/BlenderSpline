Spline is a simple and classic way to draw and edit splines in Blender. Draw native Bézier curves with straight edges and smooth arcs, then edit vertices, segments, individual splines, or the whole curve in the 3D Viewport.

## Start drawing a spline

1. Switch to **Object Mode** in the **3D Viewport**.
2. Choose **Add → Curve → Draw Spline**, or open the **Spline** sidebar tab and click **Draw Spline**. Open the sidebar with **N** in the Default keymap or **Ctrl+]** in Industry Compatible.
3. Click to place a corner. Click-drag to pull linked Bézier handles. The starting view fixes the drawing plane at the 3D cursor's depth.
4. Right-click or press **Enter** after at least two vertices to finish an open path. To close a path with at least three vertices, click its first vertex; click-drag there to adjust its closing handles.

Hold **Shift** for 45° direction steps, or to snap the first point to the drawing-plane grid. **Backspace** or **Ctrl+Z** removes the last preview point. **Esc** cancels the unfinished drawing. Orbit, pan, and zoom remain available.

## Select and edit

Select a Bézier curve in Object Mode and press **6**, or click **Edit Spline** in the sidebar. Keep the pointer over the 3D Viewport when using shortcuts. With several objects selected, **6 / Edit Active** edits the active Bézier curve by itself.

| Key / button | Action |
| --- | --- |
| **1 Vertex** | Select and edit anchors; drag handle diamonds directly. |
| **2 Segment** | Select the spans between anchors. A selection box includes any span it touches. |
| **3 Spline** | Select an individual open or closed path in the active curve object. |
| Sidebar **All** | Select all source paths in the active curve object. |
| **Q** | Select. |
| **W** | Move. |
| **E** | Rotate. Vertex mode offers Group and Tangents. |
| **R** | Scale. Vertex mode scales tangent handles around each anchor. |
| **Shift-click** | Add or remove components from the selection. |
| **Right-click** while idle | Choose Corner, Smooth, Bézier, or Bézier Corner. |
| **4 / Enter / Numpad Enter** | Return to Object Mode. |
| **Esc** | Cancel an active drag; exit Spline editing when idle. |
| **Ctrl+Z** | Undo a completed edit. |

With one editable Bézier curve selected in Object Mode, **1**, **2**, and **3** also enter their editing levels directly with Q Select active. Essential actions have sidebar buttons or context-menu entries. Use Blender Object Mode to transform the object and its origin.

## More tools

- Insert and remove vertices, remove segments, break vertices, weld open endpoints, and flatten selected geometry with **Make Planar**.
- In Object Mode, **Attach Curves** combines selected Bézier objects into the active object while keeping their paths separate. In **3 Spline**, **Detach** moves selected paths into a separate curve object.
- In Object Mode, enable **Make Profile** and choose a live **Rectangle** or **Circle** sweep. Rectangle provides Height, Width, and Roll; Circle provides Radius. **Curve Resolution** controls smoothness along curved spans.
- Save normally as a `.blend`. The source curves remain native editable Bézier geometry, including after disabling the extension.

Spline edits one all-Bézier curve object at a time. Tight or intersecting profile sweeps can overlap. See the [full user guide and current development notes](https://github.com/kielpease/BlenderSpline/blob/main/docs/USER_GUIDE.md) and [feature demos](https://github.com/kielpease/BlenderSpline#feature-demos).

By **Pease Technology**. Licensed under **GPL-3.0-or-later**. Published version 1.0.0 was tested on Blender **5.2.4 LTS for Windows** with Default and Industry Compatible keymaps. Compatibility outside the recorded test environments is unverified.
