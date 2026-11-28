# Publishing Spline updates

The public distribution is [Spline on Blender Extensions](https://extensions.blender.org/add-ons/spline-maker/). Version 1.0.0 was listed as approved when checked on 2026-11-27. Keep the manifest ID `spline_maker`; the public URL slug is `spline-maker`.

Every owner-accepted public update must reach this existing listing. A code push or a local stable ZIP alone does not distribute an update. Publishing a stable GitHub release triggers `.github/workflows/blender-extensions.yml`, which uploads the attached, tested ZIP and the GitHub release notes using [Blender's documented upload API](https://developer.blender.org/docs/features/extensions/ci_cd/). Drafts and prereleases are excluded. Upload acceptance and public availability are separate states; check the platform version/status after each upload.

## One-time account setup

1. Sign into Blender Extensions with the Blender ID that owns Spline (the current listing credits Kiel-Matthew-Pease). Generate an authentication token from the account profile, as described in the API documentation.
2. In `kielpease/BlenderSpline` on GitHub, open **Settings → Secrets and variables → Actions → New repository secret**. Name it **BLENDER_EXTENSIONS_TOKEN** and store the token there. Do not paste tokens into chat, tracked files, release notes, or shell commands.
3. Ensure GitHub Actions is enabled and these workflows have been committed and pushed before creating the next release tag. Workflow permissions need only repository contents read access; the Blender token authorizes the external upload.

This repository change does not create the account token or configure the GitHub secret. Until those steps are complete, automatic uploads will fail explicitly. The workflow does not publish the already-listed 1.0.0 again.

## For every update

1. Implement the focused change and increase `version` in `extension/spline_maker/blender_manifest.toml` to a new stable `X.Y.Z` greater than the latest published version. Never reuse a released version. Add user-facing notes under **Unreleased** in `CHANGELOG.md`, then move them to a dated version entry for release. Update relevant user/build docs.
2. On a Windows machine with Blender **5.2.4 LTS**, prepare the candidate from the repository root:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Prepare-Release.ps1 -Blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
   ```

   This validates source, builds `dist/spline-X.Y.Z.zip`, validates the ZIP, runs the existing background suite in a fresh isolated profile, and checks package identity, version, file contents, and license against source. It stops on failure, preserves an existing ZIP, and restores `BLENDER_USER_RESOURCES`. Keep its logs and SHA256. It does not upload anything.

   On this work laptop Blender is 5.2.5 LTS. Add `-ExpectedBlenderVersion 5.2.5` to use it explicitly and record 5.2.5 in the results. This does not establish that new behavior has passed on 5.2.4. Other Blender minor versions require a separate compatibility decision.
3. Test **that exact ZIP** in clean Blender profiles with Default and Industry Compatible keymaps. Follow the [release gate](TEST_PLAN.md#release-gate), covering drawing, mode entry/exit, selection, transform/topology Undo/Redo, live profiles, save/reopen, and cleanup. Record the exact Blender version, background results, UI cases checked, remaining limits, and owner acceptance in `docs/TEST_PLAN.md`. Synthetic release checks do not verify Blender behavior.
4. Commit the accepted source and documentation. From the clean accepted checkout, rerun `scripts/Check-Release.ps1 -Tag vX.Y.Z -Archive dist/spline-X.Y.Z.zip`. Create and push tag **vX.Y.Z** at that commit. The checker requires the tag, manifest version, and ZIP contents to agree. Preserve the same tested asset; do not rebuild it after UI acceptance.
5. Create a **draft GitHub release** for that tag. Attach **spline-X.Y.Z.zip** and paste the corresponding user-facing changelog into its release notes, including known limitations and tested compatibility. Do not attach GitHub's source archive as the extension. Promote the accepted ZIP to `stable/spline_maker-stable.zip` using the [local installer procedure](BUILD.md#stable-local-installer).
6. Publish the GitHub release as a stable release. This is the upload trigger. The workflow downloads the attached ZIP, checks it against tagged source, and sends it with the release notes to the existing Blender Extensions listing. It does not build a replacement ZIP. Check **Actions → Publish Blender Extensions update** for success and the verified SHA256.
7. Open the [platform version history](https://extensions.blender.org/add-ons/spline-maker/versions/). Confirm the version, release notes, status, and download. If moderation is required, track it until approval. In Blender, refresh the official repository's extension updates and verify an existing installation can update to this version. Record the platform result and update test in `docs/TEST_PLAN.md`; only then mark distribution complete.

## Failed uploads and corrections

The listing's About text is maintained separately from release notes. Its source is `docs/EXTENSIONS_DESCRIPTION.md`; update it through **Edit** on the existing listing and verify the public page afterward. Describe publicly available features there; add candidate controls after release. Supported discovery tags are declared in the manifest and reach the listing with the uploaded version. Use accepted tags such as **Add Curve**, **Modeling**, and **3D View**; include Bézier and workflow terms naturally in the description rather than inventing unsupported tags.

Inspect the platform before retrying: a timeout may occur after an upload was accepted. If the version is absent, fix the secret, release asset, or notes and rerun the failed workflow job. Do not repeatedly upload a version already present. For a code fix, use a new version and repeat testing.

If the API is unavailable, sign into the existing Spline listing and use its new-version upload action with the **same tested ZIP** and release notes. Record the manual upload and verify publication/update delivery as above. Do not create a second listing. Keep the previous known-good version available; publish a higher patch version to correct a bad release.

## Process verification

Run `powershell -NoProfile -ExecutionPolicy Bypass -File tests/release_checks.ps1` to exercise the package safeguards with synthetic ZIPs. The execution-policy flag applies only to this process; it leaves the laptop's saved policy unchanged. GitHub also runs these checks on relevant pushes and pull requests. They cover tag mismatch, prerelease rejection, wrong identity/version/metadata, missing license, duplicate/extra files, and altered source bytes. They do not call Blender or the publishing API.

Initial status on 2026-11-27: local release-tool checks are recorded in `TEST_PLAN.md`. Real Blender preparation, GitHub-hosted workflow execution, token configuration, API upload, moderation, and the end-user update path remain unverified for this new process. No new extension version is being released by this process change.

Later on 2026-11-27, the 1.1.0 feature candidate passed source/ZIP validation and the full background suite on the work laptop's installed Blender 5.2.5 LTS, and selected viewport cases were checked. The live About text was updated successfully. Owner acceptance, live tags (which require the new package), API workflow execution, and update delivery remain pending. See `TEST_PLAN.md` for the exact limits.

The owner subsequently accepted 1.1.0 and authorized distribution. GitHub release `v1.1.0` is public and the same ZIP is the local stable installer. The publishing workflow passed asset verification but cannot upload until `BLENDER_EXTENSIONS_TOKEN` is configured. The manual fallback has the tested ZIP selected and is waiting for explicit confirmation of the form's Terms of Service acceptance. See the distribution entry in `TEST_PLAN.md` for current publication status.
