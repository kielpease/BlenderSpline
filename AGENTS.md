# Project instructions

## Product and scope

Build Spline Maker, a Blender extension for direct spline drawing and editing. Read `docs/INTERACTION_SPEC.md`, `docs/ROADMAP.md`, and the current issue before editing. Primary target is Blender 5.2.4 LTS on Windows. This repository initially contains planning only; do not claim features exist until implemented and tested.

Implement the requested issue only, plus necessary dependencies. Do not implement future wall rendering, attaching, welding, or topology editing early. Preserve native editable Bézier curves where practical. Do not silently convert source curves to meshes.

## Interaction rules

- Click corners; click-drag Bézier handles; Shift constrains placement in 45-degree increments on a fixed drawing plane.
- Q/W/E/R select tools; 1/2/3/4 select component levels. Keep bindings local to this tool's context.
- All essential actions need visible buttons or contextual menu entries.
- Do not substitute a hotkey-heavy workflow for the specification.
- Distinguish breaking tangent linkage (Bézier Corner) from splitting spline topology (Break).
- Closed-region selection is a logical spline region, not editable generated mesh faces.
- Menu entry is required; investigate the toolbar Add flyout separately rather than claiming both use the same API.
- Unregister must clean up classes, menus, tools, keymaps, handlers, and draw callbacks owned by the extension.

## Engineering

Use Python and Blender's supported extension APIs. Verify version-specific APIs against official documentation and the installed Blender. Keep math/state logic separate from viewport/UI code. Prefer small modules with clear ownership. No network, external binaries, or third-party runtime dependencies for the first release.

Design reliable undo boundaries; do not assume Blender automatically records each click inside a long-running modal operator. Support cancel rollback and guard against stale data references after undo. Keep viewport navigation available. Persist only document settings that belong in the .blend file; clear temporary session state on tool exit.

## Validation and reporting

Run focused math tests and Blender background smoke tests when relevant. Mouse interaction, gizmos, picking, and navigation require real Blender UI testing. Never equate syntax checks or mocks with UI verification. Report exact Blender version, checks run, and anything untested.

For each change: summarize behavior, files changed, tests, limitations, and a short user test procedure. Update relevant docs and changelog when present. Do not increase scope or make unsupported compatibility claims to satisfy a milestone.
