# Spline Maker for Blender

Planning starter for a Blender extension inspired by the direct spline modeling workflow of 3ds Max. Working title: **Spline Maker**. Suggested GitHub repository: `blender-spline-maker`.

**Status:** The owner accepted SM-009 selection, SM-010 vertex types/Undo, and the 0.10.3 interaction follow-up. All-tool box selection, direct handle dragging, and planar/view-plane vertex Move controls are accepted in the viewport. Package validation and background checks pass on Blender 5.2.4 LTS. Next: SM-011 segment selection.

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
| 1 / 2 / 3 / 4 | Vertex / Segment / Closed region / Whole curve |
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
