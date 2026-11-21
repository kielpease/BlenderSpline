# Splines for Blender

Splines is a Blender extension for drawing and editing native Bézier curves, inspired by the direct spline modeling workflow of 3ds Max.

**Status:** The stable installer contains version 0.15.2. The owner accepted the 0.15.8 Bézier closure workflow. The 0.16.0 test build integrates viewport navigation with active drags and records a native Undo checkpoint when entering Edit Mode. See `docs/BUILD.md` for the local build and viewport checks.

Primary test target: Blender 5.2.4 LTS on Windows. Compatibility beyond that version is unverified.

## Goal

Draw and edit mixed straight/Bézier outlines without memorizing an add-on-specific command system. Use visible tools, contextual menus, familiar transforms, and predictable selections.

## Agreed interaction

| Input | Behavior |
| --- | --- |
| Add → Curve → Draw Spline | Start drawing on a plane aligned to the starting view |
| Left click | Place corner vertex |
| Left click and drag | Place Bézier vertex and pull its tangent handles |
| Shift during placement | Constrain segment direction to 45-degree increments in the drawing plane |
| Click first vertex | Close spline when enough vertices exist |
| Click and drag from first vertex | Close the spline and set linked Bézier handles at the seam |
| Q / W / E / R | Select / Move / Rotate / Scale |
| 1 / 2 / 3 / 4 in Edit Mode | Vertex / Segment / Spline (auto-select a sole spline) / All source splines |
| Enter or Finish Editing | Return to Object Mode from Spline Maker Edit |
| 5 | Preserve the owner's native Blender mode control |
| 1 or 6 from Object Mode / Edit Spline button | Enter Vertex editing with Q Select active for a single selected editable Bezier curve |
| Right click while editing | Vertex types and other selection-relevant commands |

Shortcuts supplement visible controls. They must be scoped to Spline Maker tools and must not replace Blender's global keymap.

Q is also an explicit Select entry from supported native Curve Edit tools. W/E/R retain their native behavior until a Spline Maker tool is active. Meshes and other unsupported contexts retain native 1/6/Q controls.

## Project files

- `extension/spline_maker/`: extension manifest, registration, and viewport entry points.
- `tests/blender/smoke_registration.py`: background installation and registration smoke test.
- `docs/BUILD.md`: build, install, and verification instructions.
- `docs/ROADMAP.md`: milestones, issue-sized tasks, and release gates.
- `docs/INTERACTION_SPEC.md`: behavior contract and decisions to validate.
- `docs/ARCHITECTURE.md`: proposed implementation and technical risks.
- `docs/TEST_PLAN.md`: manual acceptance tests and meaningful automated checks.
- `docs/CODEX_WORKFLOW.md`: repository setup and copy/paste development prompts.
- `AGENTS.md`: persistent project guidance for Codex.

## Release approach

First prove drawing, then selection and transforms. Deliver installable test builds at each working milestone. Height/width rendering and advanced topology operations follow a usable editing release.

License and final public name remain decisions for the owner. Do not distribute copied third-party code without reviewing its license. Public visibility and extension publication are separate from development.
