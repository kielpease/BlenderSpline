# Run with: powershell -NoProfile -ExecutionPolicy Bypass -File tests/release_checks.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$sourceRoot = Join-Path $repoRoot 'extension/spline_maker'
$manifest = Get-Content (Join-Path $sourceRoot 'blender_manifest.toml') -Raw
$version = [regex]::Match($manifest, '(?m)^version\s*=\s*"([^"]+)"\s*$').Groups[1].Value
$pathsBlock = [regex]::Match($manifest, '(?s)\[build\]\s*paths\s*=\s*\[(.*?)\]').Groups[1].Value
$paths = @([regex]::Matches($pathsBlock, '"([^"]+)"') | ForEach-Object { $_.Groups[1].Value })
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$testRoot = Join-Path $repoRoot ('dist/release-checks-' + [guid]::NewGuid().ToString())
New-Item -ItemType Directory $testRoot -Force | Out-Null
$archive = Join-Path $testRoot "spline-$version.zip"
function New-TestArchive([string]$Variant) {
    $zip = [IO.Compression.ZipFile]::Open($archive, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $metadata = $manifest
        if ($Variant -eq 'wrong-id') { $metadata = $metadata.Replace('id = "spline_maker"', 'id = "other"') }
        if ($Variant -eq 'wrong-version') { $metadata = $metadata.Replace("version = `"$version`"", 'version = "99.0.0"') }
        if ($Variant -eq 'wrong-metadata') { $metadata = $metadata.Replace('name = "Spline"', 'name = "Other"') }
        $writer = [IO.StreamWriter]::new($zip.CreateEntry('blender_manifest.toml').Open())
        try { $writer.Write($metadata) } finally { $writer.Dispose() }
        foreach ($path in $paths) {
            if ($Variant -eq 'missing-license' -and $path -eq 'LICENSE') { continue }
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $sourceRoot $path), $path) | Out-Null
        }
        if ($Variant -eq 'duplicate') { $zip.CreateEntry('LICENSE') | Out-Null }
        if ($Variant -eq 'extra') { $zip.CreateEntry('unexpected.py') | Out-Null }
    } finally { $zip.Dispose() }
}
function Assert-Rejected([string]$Tag, [string]$Reason) {
    $rejected = $false
    try { & "$repoRoot/scripts/Check-Release.ps1" -Tag $Tag -Archive $archive | Out-Null }
    catch { $rejected = $true }
    if (-not $rejected) { throw "Expected rejection: $Reason" }
}

New-TestArchive 'valid'
$result = & "$repoRoot/scripts/Check-Release.ps1" -Tag "v$version" -Archive $archive
if ($result.Version -cne $version -or $result.SHA256 -notmatch '^[a-f0-9]{64}$') { throw 'Valid asset verification failed.' }
Assert-Rejected 'v99.0.0' 'tag mismatch'
Assert-Rejected "$version" 'missing v prefix'
Assert-Rejected "v$version-rc.1" 'prerelease tag'
$count = 4
foreach ($variant in @('wrong-id', 'wrong-version', 'wrong-metadata', 'missing-license', 'duplicate', 'extra')) {
    # Each generated file stays in this unique workspace test directory.
    Remove-Item -LiteralPath $archive
    New-TestArchive $variant
    Assert-Rejected "v$version" $variant
    $count++
}
Remove-Item -LiteralPath $archive
New-TestArchive 'valid'
# Same-length content corruption still has to fail source verification.
$zip = [IO.Compression.ZipFile]::Open($archive, [IO.Compression.ZipArchiveMode]::Update)
try {
    $zip.GetEntry('__init__.py').Delete()
    $writer = [IO.StreamWriter]::new($zip.CreateEntry('__init__.py').Open())
    try { $writer.Write('# stale or altered release source') } finally { $writer.Dispose() }
} finally { $zip.Dispose() }
Assert-Rejected "v$version" 'altered source file'
$count++
Write-Host "$count release checks passed. Synthetic ZIP fixtures retained at $testRoot"
