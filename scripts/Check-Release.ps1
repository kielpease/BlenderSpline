param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Archive
)

# Verify the exact release asset before handing it to Blender Extensions.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$sourceRoot = Join-Path $repoRoot 'extension/spline_maker'
$sourceManifest = Get-Content -LiteralPath (Join-Path $sourceRoot 'blender_manifest.toml') -Raw
$versionMatch = [regex]::Match($sourceManifest, '(?m)^version\s*=\s*"([^"]+)"\s*$')
$version = $versionMatch.Groups[1].Value
if ($version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$' -or $Tag -cne "v$version") {
    throw "Release tag must be v<manifest version> with a stable X.Y.Z version; got '$Tag'."
}
if (-not $Archive) { $Archive = Join-Path $repoRoot "dist/spline-$version.zip" }
$archivePath = (Resolve-Path -LiteralPath $Archive).Path
if ((Split-Path $archivePath -Leaf) -cne "spline-$version.zip") {
    throw "Expected asset name spline-$version.zip."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
function Read-ZipText($Entry) {
    $reader = [System.IO.StreamReader]::new($Entry.Open())
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}
function Get-StreamHash($Stream) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($Stream)) }
    finally { $sha.Dispose(); $Stream.Dispose() }
}

$zip = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
try {
    $entries = @{}
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName.EndsWith('/')) { continue }
        if ($entries.ContainsKey($entry.FullName)) { throw "Duplicate ZIP path: $($entry.FullName)" }
        $entries[$entry.FullName] = $entry
    }
    if (-not $entries.ContainsKey('blender_manifest.toml')) { throw 'ZIP must contain a root manifest.' }
    $packedManifest = Read-ZipText $entries['blender_manifest.toml']
    # Blender may rewrite build metadata; public extension metadata must match.
    $buildHeader = [regex]::new('(?m)^\[build(?:\.|\])')
    $sourceMetadata = ($buildHeader.Split($sourceManifest, 2)[0] -replace "`r`n", "`n").Trim()
    $packedMetadata = ($buildHeader.Split($packedManifest, 2)[0] -replace "`r`n", "`n").Trim()
    if ($sourceMetadata -cne $packedMetadata) { throw 'ZIP metadata differs from tagged source.' }
    foreach ($manifest in @($sourceManifest, $packedManifest)) {
        if ($manifest -cnotmatch '(?m)^id\s*=\s*"spline_maker"\s*$') { throw 'Extension ID must remain spline_maker.' }
        if ($manifest -cnotmatch ('(?m)^version\s*=\s*"' + [regex]::Escape($version) + '"\s*$')) { throw 'ZIP/source version mismatch.' }
        if ($manifest -cnotmatch '(?m)^license\s*=\s*\[\s*"SPDX:GPL-3\.0-or-later"\s*\]\s*$') { throw 'Expected GPL-3.0-or-later license.' }
    }
    $pathsMatch = [regex]::Match($sourceManifest, '(?s)\[build\]\s*paths\s*=\s*\[(.*?)\]')
    if (-not $pathsMatch.Success) { throw 'Expected an explicit manifest build.paths list.' }
    $paths = @([regex]::Matches($pathsMatch.Groups[1].Value, '"([^"]+)"') | ForEach-Object { $_.Groups[1].Value })
    if ($paths -cnotcontains 'LICENSE' -or $paths -cnotcontains '__init__.py') { throw 'Build must include LICENSE and __init__.py.' }
    foreach ($path in $paths) {
        if ($path -match '(^[/\\]|(^|[/\\])\.\.([/\\]|$)|:)') { throw "Invalid build path: $path" }
        if (-not $entries.ContainsKey($path)) { throw "ZIP is missing $path." }
        $expected = Get-StreamHash ([System.IO.File]::OpenRead((Join-Path $sourceRoot $path)))
        $actual = Get-StreamHash ($entries[$path].Open())
        if ($expected -cne $actual) { throw "ZIP differs from tagged source: $path" }
    }
    if ($entries.Count -ne $paths.Count + 1) { throw 'ZIP contains files outside manifest build.paths.' }
    $rootLicense = Get-FileHash -LiteralPath (Join-Path $repoRoot 'LICENSE') -Algorithm SHA256
    $packageLicense = Get-FileHash -LiteralPath (Join-Path $sourceRoot 'LICENSE') -Algorithm SHA256
    if ($rootLicense.Hash -cne $packageLicense.Hash) { throw 'Repository and package licenses differ.' }
} finally { $zip.Dispose() }

[pscustomobject]@{
    Version = $version
    Archive = $archivePath
    SHA256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
}
