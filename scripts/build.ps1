Param(
    [string]$Version,
    [string]$FolderName = "render_queue_manager"
)

$ErrorActionPreference = 'Stop'

# Derive version from __init__.py if not supplied
if (-not $Version) {
    $rootInit = Join-Path $PSScriptRoot '..' '__init__.py'
    $content = Get-Content $rootInit -Raw
    if ($content -match "version': \(([^\)]+)\)") {
        $tuple = $Matches[1] -replace '[^0-9,]',''
        $Version = ($tuple -split ',')[0..2] -join '.'
    } else {
        throw "Could not parse version from __init__.py"
    }
}

Write-Host "Building Render Queue Manager v$Version" -ForegroundColor Cyan

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dist = Join-Path $repoRoot 'dist'
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
New-Item -ItemType Directory -Path $dist | Out-Null

$staging = Join-Path $dist $FolderName
New-Item -ItemType Directory -Path $staging | Out-Null

Copy-Item (Join-Path $repoRoot '__init__.py') $staging
Copy-Item (Join-Path $repoRoot 'README.md') $staging
Copy-Item (Join-Path $repoRoot 'CHANGELOG.md') $staging
Copy-Item (Join-Path $repoRoot 'LICENSE') $staging
Copy-Item -Recurse -Destination (Join-Path $staging 'rqm') -Path (Join-Path $repoRoot 'rqm')

$zipName = "render-queue-manager-v$Version.zip"
$zipPath = Join-Path $repoRoot $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Compress-Archive -Path $staging -DestinationPath $zipPath -Force

Write-Host "Created $zipName" -ForegroundColor Green
Get-FileHash $zipPath -Algorithm SHA256 | Format-Table -AutoSize
