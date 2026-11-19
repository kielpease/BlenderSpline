# Proposed architecture

## Foundation

Use native Blender Bézier curve data as persistent source geometry. Implement custom interaction around it. Prefer a standard Blender extension with `blender_manifest.toml`, explicit registration, and no external runtime dependencies. Confirm APIs against Blender 5.2.4 LTS before implementation.

Keep document state (source curves and relevant settings) separate from transient interaction state (hover target, live preview, drag start, drawing plane during creation). Native curve data must remain usable if the add-on is disabled.

## Source layout

SM-001 implements the extension entry point, manifest, viewport UI, and background smoke test. The remaining paths below are proposed.

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

**Menu integration.** Add → Curve is straightforward in concept; the toolbar Add flyout is a distinct integration problem. Document what's supported without patching Blender internals.

## Later geometry

Profile generation may use Geometry Nodes or a controlled mesh generator. Choose after testing planar corner joins and alignment. Do not assume a rectangular Curve to Mesh sweep alone preserves wall thickness at every corner. Source curve remains editable; generated geometry is derived output. Height and width stay unit-aware settings independent of path vertex edits.

## Reference documentation

- Blender extension format: https://docs.blender.org/manual/en/5.2/advanced/extensions/getting_started.html
- Extension build CLI: https://docs.blender.org/manual/en/5.2/advanced/command_line/extension_arguments.html
- Use Blender's version-matched Python API documentation during implementation.
