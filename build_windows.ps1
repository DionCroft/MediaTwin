param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

if (-not $SkipInstall) {
    Write-Host "Installing dependencies..."
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements.txt
}

$IconArgs = @()
$IconPath = Join-Path $ProjectRoot "assets\app_icon.ico"
if (Test-Path $IconPath) {
    $IconArgs = @("--icon", $IconPath)
}

Write-Host "Building Media Duplicate Finder..."
& $VenvPython -m PyInstaller `
    --noconfirm `
    --windowed `
    --name "Media Duplicate Finder" `
    --add-data "assets;assets" `
    @IconArgs `
    "video_duplicate_finder\gui\app.py"

Write-Host ""
Write-Host "Build complete: dist\Media Duplicate Finder\Media Duplicate Finder.exe"
