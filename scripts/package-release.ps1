[CmdletBinding()]
param(
  [string]$Version = '',
  [switch]$SkipBuild
)

# NOTE: the frontend builds with base=/moxi/ (one-domain subpath deploy).
#       For the current runbook see ../deploy/README.md at the repo root.

# Builds a deployable bundle:
#   release/<version>/sites/moxi   -> static files for Nginx
#   release/<version>/...          -> API image sources + nginx samples
#   release/moxi-<version>.zip     -> what you upload to the server
#
# Output messages stay ASCII on purpose: Windows PowerShell 5.1 reads
# BOM-less .ps1 files as ANSI and would mangle Chinese text.

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$backendRoot = Join-Path $projectRoot 'backend'

if (-not $Version) {
  $pkg = Get-Content -LiteralPath (Join-Path $frontendRoot 'package.json') -Raw | ConvertFrom-Json
  $Version = $pkg.version
}

if ($Version -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]*$') {
  throw "Invalid version string: $Version"
}

$distPath = Join-Path $frontendRoot 'dist'

if (-not $SkipBuild) {
  Push-Location $frontendRoot
  try {
    if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules'))) {
      Write-Host 'Installing frontend dependencies...'
      & npm ci
      if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    }

    Write-Host 'Building frontend...'
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'npm run build failed.' }
  }
  finally {
    Pop-Location
  }
}

if (-not (Test-Path -LiteralPath (Join-Path $distPath 'index.html'))) {
  throw "Missing build output: $distPath\index.html"
}

$stage = Join-Path $projectRoot ("release\" + $Version)
if (Test-Path -LiteralPath $stage) {
  Remove-Item -LiteralPath $stage -Recurse -Force
}
$sitePath = Join-Path $stage 'sites\moxi'
New-Item -ItemType Directory -Path $sitePath -Force | Out-Null

Write-Host 'Copying static site...'
Copy-Item -Path (Join-Path $distPath '*') -Destination $sitePath -Recurse -Force

Write-Host 'Copying backend sources...'
$backendDest = Join-Path $stage 'backend'
New-Item -ItemType Directory -Path $backendDest -Force | Out-Null
Copy-Item -Path (Join-Path $backendRoot 'app') -Destination $backendDest -Recurse -Force
Copy-Item -Path (Join-Path $backendRoot 'requirements.txt') -Destination $backendDest -Force

# Strip bytecode caches copied along with the package tree.
Get-ChildItem -Path $backendDest -Recurse -Directory -Filter '__pycache__' |
  Remove-Item -Recurse -Force

Write-Host 'Copying deployment files...'
Copy-Item -Path (Join-Path $projectRoot 'Dockerfile') -Destination $stage -Force
Copy-Item -Path (Join-Path $projectRoot 'docker-compose.yml') -Destination $stage -Force
Copy-Item -Path (Join-Path $projectRoot 'deploy') -Destination $stage -Recurse -Force

$zipPath = Join-Path $projectRoot ("release\moxi-" + $Version + ".zip")
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal

$sizeKb = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1KB)
Write-Host ''
Write-Host ("Bundle : " + $zipPath)
Write-Host ("Size   : " + $sizeKb + " KB")
Write-Host 'Deploy : see deploy/nginx/README.md'
