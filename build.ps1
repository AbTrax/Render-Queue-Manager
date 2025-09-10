Param(
    [string]$Version = "1.10.5",
    [string]$FolderName = "render_queue_manager"
)

$ErrorActionPreference = 'Stop'

Write-Host "Building Render Queue Manager v$Version" -ForegroundColor Cyan

$dist = Join-Path -Path $PSScriptRoot -ChildPath 'dist'
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
New-Item -ItemType Directory -Path $dist | Out-Null

$staging = Join-Path $dist $FolderName
New-Item -ItemType Directory -Path $staging | Out-Null

# Copy files
Copy-Item (Join-Path $PSScriptRoot '__init__.py') $staging
Copy-Item (Join-Path $PSScriptRoot 'README.md') $staging
Copy-Item (Join-Path $PSScriptRoot 'CHANGELOG.md') $staging
Copy-Item (Join-Path $PSScriptRoot 'LICENSE') $staging
Copy-Item -Recurse -Destination (Join-Path $staging 'rqm') -Path (Join-Path $PSScriptRoot 'rqm')

$zipName = "render-queue-manager-v$Version.zip"
$zipPath = Join-Path $PSScriptRoot $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Compress-Archive -Path $staging -DestinationPath $zipPath -Force

Write-Host "Created $zipName" -ForegroundColor Green

# Hashes
Get-FileHash $zipPath -Algorithm SHA256 | Format-Table -AutoSize

Write-Host "Done." -ForegroundColor Cyan
