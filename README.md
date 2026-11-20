# Spline Maker for Blender

Spline Maker is a Blender extension for drawing and editing native Bezier curves, inspired by the direct spline modeling workflow of 3ds Max.

**Status:** Move and the 0.14.1 Segment box correction are accepted by the owner. Segment boxes select any curve span touched or crossed by the box. ZIP validation and the full background suite pass on Blender 5.2.4 LTS. Next is SM-015: Segment/Spline Rotate and Scale about the selection center.

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
| Q / W / E / R | Select / Move / Rotate / Scale |
| 1 / 2 / 3 | Vertex / Segment / Spline (auto-select a sole spline) |
| 4 | Return to Object Mode |
| Whole curve button | Select all source splines, then W moves their geometry together |
| 5 | Preserve the owner's native Blender mode control |
| 6 / Edit Spline button | Enter Spline Maker Vertex editing for a single selected editable Bezier curve |
| Right click while editing | Vertex types and other selection-relevant commands |

Shortcuts supplement visible controls. They must be scoped to Spline Maker tools and must not replace Blender's global keymap.

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
