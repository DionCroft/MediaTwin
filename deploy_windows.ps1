param(
    [switch]$SkipInstall,
    [switch]$SkipTests,
    [switch]$SkipBuild,
    [switch]$NoArchive,
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$AppName = "Media Duplicate Finder"
$SafeAppName = "MediaDuplicateFinder"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
$ReleaseDir = Join-Path $ProjectRoot "release"
$AppDistDir = Join-Path $DistDir $AppName
$AppExe = Join-Path $AppDistDir "$AppName.exe"

function Remove-WorkspaceItem {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $workspace = (Resolve-Path -LiteralPath $ProjectRoot).Path
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $resolved.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside workspace: $resolved"
    }

    Remove-Item -LiteralPath $resolved -Recurse -Force
}

function Compress-WithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [int]$Attempts = 8,
        [int]$DelaySeconds = 2
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            if (Test-Path -LiteralPath $DestinationPath) {
                Remove-WorkspaceItem $DestinationPath
            }
            Compress-Archive -Path $SourcePath -DestinationPath $DestinationPath -Force
            return
        } catch {
            if ($attempt -eq $Attempts) {
                throw
            }
            Write-Host "Archive attempt $attempt failed because a file is busy. Retrying..."
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

if (-not $Version) {
    $Version = Get-Date -Format "yyyyMMdd-HHmm"
}

Write-Host "Preparing $AppName deployment..."

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

if (-not $SkipInstall) {
    Write-Host "Installing dependencies..."
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements.txt
}

if (-not $SkipTests) {
    Write-Host "Running compile check..."
    & $VenvPython -B -m compileall -q video_duplicate_finder tests

    Write-Host "Running tests..."
    & $VenvPython -B -m pytest
}

if (-not $SkipBuild) {
    Write-Host "Cleaning previous build output..."
    Remove-WorkspaceItem $BuildDir
    Remove-WorkspaceItem $DistDir

    Write-Host "Building Windows app..."
    & powershell -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "build_windows.ps1") -SkipInstall

    if (-not (Test-Path -LiteralPath $AppExe)) {
        throw "Expected build output was not created: $AppExe"
    }
}

if (-not $NoArchive -and -not $SkipBuild) {
    Write-Host "Creating release archive..."
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

    $ArchivePath = Join-Path $ReleaseDir "$SafeAppName-windows-$Version.zip"
    $ChecksumPath = "$ArchivePath.sha256.txt"

    if (Test-Path -LiteralPath $ArchivePath) {
        Remove-WorkspaceItem $ArchivePath
    }
    if (Test-Path -LiteralPath $ChecksumPath) {
        Remove-WorkspaceItem $ChecksumPath
    }

    Compress-WithRetry -SourcePath $AppDistDir -DestinationPath $ArchivePath
    $Hash = Get-FileHash -Path $ArchivePath -Algorithm SHA256
    "$($Hash.Hash)  $(Split-Path -Leaf $ArchivePath)" | Set-Content -Path $ChecksumPath -Encoding UTF8

    Write-Host ""
    Write-Host "Deploy complete:"
    Write-Host "  App:     $AppExe"
    Write-Host "  Archive: $ArchivePath"
    Write-Host "  SHA256:  $ChecksumPath"
} elseif (-not $SkipBuild) {
    Write-Host ""
    Write-Host "Deploy complete:"
    Write-Host "  App: $AppExe"
} else {
    Write-Host ""
    Write-Host "Deploy dry run complete. Build and archive were skipped."
}
