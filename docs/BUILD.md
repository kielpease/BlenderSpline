# Build and test Spline Maker

SM-001 targets Blender 5.2.4 LTS on Windows. The ZIP is for local testing. The manifest carries a license placeholder until the owner selects a license and updates the metadata for distribution.

## Build and validate

Run from the project folder in PowerShell. Set `$blender` to your installed executable.

```powershell
$blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
New-Item -ItemType Directory -Force dist | Out-Null
& $blender --command extension validate extension/spline_maker
& $blender --command extension build --source-dir extension/spline_maker --output-dir dist
& $blender --command extension validate dist/spline_maker-0.1.0.zip
```

Blender writes the ZIP to `dist/spline_maker-0.1.0.zip` using its [extension packaging commands](https://docs.blender.org/manual/en/5.2/advanced/command_line/extension_arguments.html).

## Background smoke test

Use the same PowerShell session. The test installs the ZIP into a fresh profile under `dist` and restores the previous environment setting afterward.

```powershell
$previousResources = $env:BLENDER_USER_RESOURCES
try {
    $testProfile = Join-Path (Resolve-Path dist) ([guid]::NewGuid().ToString())
    $env:BLENDER_USER_RESOURCES = (New-Item -ItemType Directory $testProfile).FullName
    & $blender --background --factory-startup --python-exit-code 1 --python tests/blender/smoke_registration.py -- dist/spline_maker-0.1.0.zip
} finally {
    $env:BLENDER_USER_RESOURCES = $previousResources
}
```

The smoke test checks install, enable, disable, and re-enable, including menu callback count, class cleanup, and the placeholder action's effect on scene objects.

## Blender viewport check

1. In **Edit → Preferences → Get Extensions**, open the top-right menu and choose **Install from Disk**. Select the ZIP and enable **Spline Maker** in **Add-ons** if needed.
2. In the 3D Viewport in Object Mode, open **Add → Curve** and confirm **Draw Spline** appears once. Click it and confirm Blender reports that spline drawing is still in development and adds no objects.
3. Press **N** over the viewport and open **Spline Maker**. Confirm the panel shows the development status and its **Draw Spline** button gives the same result.
4. Disable **Spline Maker** in **Preferences → Add-ons** and confirm both entry points disappear. Re-enable it and confirm each returns once.
