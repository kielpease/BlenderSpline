# GitHub and Codex workflow

The project now ships as Spline on [Blender Extensions](https://extensions.blender.org/add-ons/spline-maker/). Follow [Publishing Spline updates](RELEASING.md) for current versioning, acceptance, and distribution. The repository-creation and first-task prompts below are historical starter guidance.

## Create the repository

1. Choose a name, suggested `blender-spline-maker`, and public/private visibility. Keep it private initially if you want to refine it before sharing.
2. Create an empty GitHub repository. Copy the contents of this starter into its local checkout so README.md and AGENTS.md are at repository root.
3. Commit the planning files and push. Choose a project license before distributing implementation; no software license is selected by this starter.
4. Open the local repository folder in Codex. Provide the exact path to Blender 5.2.4's executable when running Blender checks. Store machine-specific paths locally, not in tracked source.
5. Create milestones M0–M4 and use the SM task descriptions from ROADMAP.md as GitHub issues. M5/M6 remain backlog.

This starter does not create a GitHub repository, issues, commits, or connections on your behalf.

## First Codex prompt

> Read AGENTS.md and all docs. Implement SM-001 only: an installable Blender 5.2.4 LTS extension shell with reliable register/unregister, Add → Curve → Draw Spline entry, and visible placeholder panel. The Draw Spline action should clearly report that drawing is not implemented yet; do not pretend it works. Add build instructions and a focused Blender registration smoke test. Do not implement drawing, remap global keys, or add geometry generation. Report checks actually performed and exact installation/test steps. If the project license is not selected, flag that metadata decision before distribution rather than inventing one.

## Second Codex prompt

> Implement SM-002 as a minimal feasibility spike. Demonstrate native Bézier vertex/handle picking, scoped Q/W/E/R tool activation, and the intended tangent-only vertex rotation/scaling. Evaluate native Edit Mode versus custom tools/gizmos. Keep the spike small and document actual UI results, limitations, and the recommended approach in an architecture decision. Do not expand into the full editor. Read AGENTS.md first.

## Repeatable issue prompt

> Read AGENTS.md, the interaction spec, and the current roadmap. Implement [SM-ID and title] only, including required dependencies already agreed in the issue. State any assumptions. Run appropriate focused checks, update affected docs, and give me a short Blender test procedure. Clearly distinguish automated verification from UI tests I still need to perform. Do not implement future milestones.

## Working loop

One focused issue per branch/change. Codex implements and checks it; the owner tests in Blender and provides exact feedback; fix the issue before moving on. Mark UI-dependent work Needs user test until accepted. Keep small reproducible test scenes and avoid committing large binary assets without a reason.

Ask Codex for a review before merging significant input-handling or geometry changes: behavior regressions, undo, keymap scope, cleanup, and API compatibility deserve particular attention.

## Bug report template

- Blender and extension version / commit:
- View orientation and mode:
- Exact steps:
- Expected result:
- Actual result:
- Reproduces in a new scene:
- Screenshot/video or minimal .blend if needed:

## Release discipline

Use versioned installable extension ZIPs, a short changelog, supported-version statement, known limitations, and clear test status. The planning ZIP itself is not an installable Blender extension.
