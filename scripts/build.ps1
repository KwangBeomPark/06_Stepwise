# Stepwise Build & Packaging Automation Script
# Usage: powershell -ExecutionPolicy Bypass -File scripts/build.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Stepwise Build Automation " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Clean previous build directories
$BuildDir = "$ProjectRoot\build"
$DistDir = "$ProjectRoot\dist"
$ReleaseDir = "$ProjectRoot\release\dist"

if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
if (!(Test-Path $ReleaseDir)) { New-Item -ItemType Directory -Force $ReleaseDir | Out-Null }

# 2. Run PyInstaller
Write-Host "[1/3] Running PyInstaller onedir build..." -ForegroundColor Yellow
$PythonExe = "$ProjectRoot\.venv\Scripts\python.exe"
if (!(Test-Path $PythonExe)) {
    $PythonExe = "python"
}

& $PythonExe -m PyInstaller "$ProjectRoot\installer\stepwise.spec" --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# 3. Calculate Build Size
$OnedirSizeMB = [math]::Round(((Get-ChildItem -Recurse "$DistDir\Stepwise" | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
Write-Host "PyInstaller onedir package built successfully at $DistDir\Stepwise ($OnedirSizeMB MB)" -ForegroundColor Green

# 4. Compile Inno Setup (if iscc is available on machine)
Write-Host "[2/3] Checking Inno Setup compiler (ISCC)..." -ForegroundColor Yellow
$IsccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
)

$IsccExe = $IsccPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($IsccExe) {
    Write-Host "Compiling installer using $IsccExe..." -ForegroundColor Cyan
    & $IsccExe "$ProjectRoot\installer\stepwise.iss"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Installer generated in $ReleaseDir" -ForegroundColor Green
    } else {
        Write-Warning "Inno Setup compilation failed with code $LASTEXITCODE."
    }
} else {
    Write-Host "Inno Setup compiler not found on system PATH. Onedir build is ready in $DistDir\Stepwise." -ForegroundColor Yellow
}

Write-Host "=========================================" -ForegroundColor Green
Write-Host " Build Process Completed Successfully! " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
