param(
    [Parameter(Mandatory = $true)][string]$Blender,
    [ValidatePattern('^5\.2\.\d+$')][string]$ExpectedBlenderVersion = '5.2.4'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    $blenderVersion = @(& $Blender --version)
    $versionPattern = '^Blender ' + [regex]::Escape($ExpectedBlenderVersion) + '(?:\s|$)'
    if ($LASTEXITCODE -ne 0 -or $blenderVersion[0] -notmatch $versionPattern) {
        throw "Release preparation requires Blender $ExpectedBlenderVersion. Record this exact version in the test results."
    }
    $manifest = Get-Content extension/spline_maker/blender_manifest.toml -Raw
    $version = [regex]::Match($manifest, '(?m)^version\s*=\s*"([^"]+)"\s*$').Groups[1].Value
    if ($version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$') { throw 'Expected a stable X.Y.Z manifest version.' }
    New-Item -ItemType Directory -Force dist | Out-Null
    $archive = "dist/spline-$version.zip"
    if (Test-Path -LiteralPath $archive) { throw "$archive already exists. Preserve tested ZIPs; move it aside before rebuilding." }
    & $Blender --command extension validate extension/spline_maker
    if ($LASTEXITCODE -ne 0) { throw 'Source validation failed.' }
    & $Blender --command extension build --source-dir extension/spline_maker --output-filepath $archive
    if ($LASTEXITCODE -ne 0) { throw 'Extension build failed.' }
    & $Blender --command extension validate $archive
    if ($LASTEXITCODE -ne 0) { throw 'ZIP validation failed.' }
    $previousResources = $env:BLENDER_USER_RESOURCES
    try {
        $testProfile = Join-Path (Resolve-Path dist).Path ([guid]::NewGuid().ToString())
        $env:BLENDER_USER_RESOURCES = (New-Item -ItemType Directory $testProfile).FullName
        & $Blender --background --factory-startup --python-exit-code 1 --python tests/blender/smoke_registration.py -- $archive
        if ($LASTEXITCODE -ne 0) { throw 'Background smoke tests failed.' }
    } finally { $env:BLENDER_USER_RESOURCES = $previousResources }
    & "$PSScriptRoot/Check-Release.ps1" -Tag "v$version" -Archive $archive
    Write-Host 'Automated preparation passed. Complete and record the release UI checklist before publishing.'
} finally { Pop-Location }
