Param(
    [string]$Version,
    [string]$FolderName
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$manifestPath = Join-Path $repoRoot 'blender_manifest.toml'
if (-not (Test-Path $manifestPath)) {
    throw "blender_manifest.toml is required to build the extension"
}

$manifestContent = Get-Content $manifestPath -Raw

if (-not $FolderName) {
    if ($manifestContent -match '^id\s*=\s*"([^"]+)"') {
        $FolderName = $Matches[1].Trim()
    }
    else {
        throw "Could not parse id from blender_manifest.toml"
    }
}

if (-not $Version) {
    if ($manifestContent -match '^version\s*=\s*"([^"]+)"') {
        $Version = $Matches[1].Trim()
    }
    else {
        throw "Could not parse version from blender_manifest.toml"
    }
}

$initPath = Join-Path $repoRoot '__init__.py'
$initContent = Get-Content $initPath -Raw
if ($initContent -match '__version__\s*=\s*"([^"]+)"') {
    $initVersion = $Matches[1].Trim()
}
else {
    throw "Could not parse __version__ from __init__.py"
}

if ($Version -ne $initVersion) {
    throw "Version mismatch: manifest/build uses $Version but __version__ is $initVersion"
}

Write-Host "Building Render Queue Manager X extension v$Version" -ForegroundColor Cyan

$dist = Join-Path $repoRoot 'dist'
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
New-Item -ItemType Directory -Path $dist | Out-Null

$staging = Join-Path $dist $FolderName
New-Item -ItemType Directory -Path $staging | Out-Null

Copy-Item (Join-Path $repoRoot '__init__.py') $staging
Copy-Item (Join-Path $repoRoot 'README.md') $staging
Copy-Item (Join-Path $repoRoot 'CHANGELOG.md') $staging
Copy-Item (Join-Path $repoRoot 'LICENSE') $staging
Copy-Item (Join-Path $repoRoot 'blender_manifest.toml') $staging
Copy-Item -Recurse -Destination (Join-Path $staging 'rqm') -Path (Join-Path $repoRoot 'rqm')
Get-ChildItem -Path (Join-Path $staging 'rqm') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Get-ChildItem -Path (Join-Path $staging 'rqm') -Recurse -Include '*.pyc','*.pyo' -File | Remove-Item -Force

$zipBaseName = $FolderName -replace '_', '-'
$zipName = "$zipBaseName-v$Version.zip"
$zipPath = Join-Path $repoRoot $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Compress-Archive -Path $staging -DestinationPath $zipPath -Force

Write-Host "Created $zipName" -ForegroundColor Green
Get-FileHash $zipPath -Algorithm SHA256 | Format-Table -AutoSize
