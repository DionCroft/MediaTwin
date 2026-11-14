param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([scriptblock]$Command, [string]$Step)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    Invoke-Checked { python -m venv .venv } "Virtual environment creation"
}

if (-not $SkipInstall) {
    Write-Host "Installing dependencies..."
    Invoke-Checked { & $VenvPython -m pip install --upgrade pip } "pip upgrade"
    Invoke-Checked { & $VenvPython -m pip install -r requirements.txt } "Dependency installation"
}

$IconArgs = @()
$IconPath = Join-Path $ProjectRoot "assets\app_icon.ico"
if (Test-Path $IconPath) {
    $IconArgs = @("--icon", $IconPath)
}

Write-Host "Building Media Duplicate Finder..."
Invoke-Checked { & $VenvPython -m PyInstaller `
    --noconfirm `
    --windowed `
    --exclude-module pytest `
    --name "Media Duplicate Finder" `
    --add-data "assets;assets" `
    @IconArgs `
    "video_duplicate_finder\gui\app.py" } "Windows build"

Write-Host ""
Write-Host "Build complete: dist\Media Duplicate Finder\Media Duplicate Finder.exe"
