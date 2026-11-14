param(
    [switch]$SkipInstall,
    [switch]$SkipTests,
    [switch]$SkipBuild,
    [switch]$NoArchive,
    [string]$Version = ""
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

    $workspace = (Resolve-Path -LiteralPath $ProjectRoot).ProviderPath.TrimEnd('\')
    $resolved = (Resolve-Path -LiteralPath $Path).ProviderPath
    if (-not $resolved.StartsWith($workspace + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside workspace: $resolved"
    }
    $current = $resolved
    while ($current -ne $workspace) {
        if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing to remove through a link or junction: $current"
        }
        $current = Split-Path -Parent $current
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
if ($Version -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') {
    throw "Version must contain only letters, numbers, dots, underscores, and hyphens (1-64 characters)."
}

Write-Host "Preparing $AppName deployment..."

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    Invoke-Checked { python -m venv .venv } "Virtual environment creation"
}

if (-not $SkipInstall) {
    Write-Host "Installing dependencies..."
    Invoke-Checked { & $VenvPython -m pip install --upgrade pip } "pip upgrade"
    Invoke-Checked { & $VenvPython -m pip install -r requirements.txt } "Dependency installation"
}

if (-not $SkipTests) {
    Write-Host "Running compile check..."
    Invoke-Checked { & $VenvPython -B -m compileall -q video_duplicate_finder tests } "Compile check"

    Write-Host "Running tests..."
    Invoke-Checked { & $VenvPython -B -m pytest } "Tests"
}

if (-not $SkipBuild) {
    Write-Host "Cleaning previous build output..."
    Remove-WorkspaceItem $BuildDir
    Remove-WorkspaceItem $DistDir

    Write-Host "Building Windows app..."
    Invoke-Checked { & powershell -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "build_windows.ps1") -SkipInstall } "Windows build"

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
