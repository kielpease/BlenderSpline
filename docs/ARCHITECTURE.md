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

The modal session owns a list of preview points. Ctrl+Z and Backspace remove the latest point from that list. Cancel discards the list and detaches the handler. Finish commits an open native Bézier curve in one Blender undo step. This lets scene undo and redo act on the finished curve as a unit. Navigation events pass through to Blender. The probe tests straight points. Click-drag handles, Shift constraints, and closure are planned for M1.

## Later geometry

Profile generation may use Geometry Nodes or a controlled mesh generator. Choose after testing planar corner joins and alignment. Do not assume a rectangular Curve to Mesh sweep alone preserves wall thickness at every corner. Source curve remains editable; generated geometry is derived output. Height and width stay unit-aware settings independent of path vertex edits.

## Reference documentation

- Blender extension format: https://docs.blender.org/manual/en/5.2/advanced/extensions/getting_started.html
- Extension build CLI: https://docs.blender.org/manual/en/5.2/advanced/command_line/extension_arguments.html
- Use Blender's version-matched Python API documentation during implementation.
