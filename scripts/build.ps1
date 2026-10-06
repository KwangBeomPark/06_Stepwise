# Stepwise Build & Packaging Automation Script (PL Suite App06)
# Usage: powershell -ExecutionPolicy Bypass -File scripts/build.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Stepwise Build Automation (App06)       " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 0. Resolve Version from pyproject.toml
$pyprojectContent = Get-Content "$ProjectRoot\pyproject.toml" -Raw
$versionMatch = [regex]::Match($pyprojectContent, 'version\s*=\s*["'']([^"'']+)["'']')
if ($versionMatch.Success) {
    $Version = $versionMatch.Groups[1].Value
} else {
    $Version = "0.2.1"
}
Write-Host "Target Version: $Version" -ForegroundColor Yellow

# 1. Clean previous build directories
$BuildDir = "$ProjectRoot\build"
$DistDir = "$ProjectRoot\dist"
$ReleaseDistDir = "$ProjectRoot\release\dist"

if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
if (!(Test-Path $ReleaseDistDir)) { New-Item -ItemType Directory -Force $ReleaseDistDir | Out-Null }

# 2. Run PyInstaller
Write-Host "[1/4] Running PyInstaller onedir build..." -ForegroundColor Yellow
$PythonExe = "$ProjectRoot\.venv\Scripts\python.exe"
if (!(Test-Path $PythonExe)) {
    $PythonExe = "python"
}

& $PythonExe -m PyInstaller "$ProjectRoot\installer\stepwise.spec" --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# 3. Calculate Build Size and create portable zip
$OnedirSizeMB = [math]::Round(((Get-ChildItem -Recurse "$DistDir\Stepwise" | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
Write-Host "PyInstaller package built at $DistDir\Stepwise ($OnedirSizeMB MB)" -ForegroundColor Green

Write-Host "[2/4] Packaging portable ZIP archive..." -ForegroundColor Yellow
$portableZip = "$ReleaseDistDir\Stepwise.v$Version.zip"
if (Test-Path $portableZip) { Remove-Item -Force $portableZip }
Compress-Archive -Path "$DistDir\Stepwise\*" -DestinationPath $portableZip -CompressionLevel Optimal
Write-Host "Portable ZIP created: $portableZip" -ForegroundColor Green

# 4. Compile Inno Setup
Write-Host "[3/4] Compiling Inno Setup installer..." -ForegroundColor Yellow
$IsccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
)

$IsccExe = $IsccPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($IsccExe) {
    $issFile = "$ProjectRoot\installer\setup.iss"
    if (!(Test-Path $issFile)) {
        $issFile = "$ProjectRoot\installer\stepwise.iss"
    }
    Write-Host "Compiling installer using $IsccExe..." -ForegroundColor Cyan
    & $IsccExe "/DMyAppVersion=$Version" $issFile
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Enterprise installer generated in $ReleaseDistDir" -ForegroundColor Green

        # 5. Create Dual Naming Alias
        Write-Host "[4/4] Generating Dual Naming artifacts..." -ForegroundColor Yellow
        $enterpriseInstaller = "$ReleaseDistDir\App06_Stepwise-Setup_v$Version.exe"
        $publicInstaller = "$ReleaseDistDir\Stepwise-Setup.v$Version.exe"

        if (Test-Path $enterpriseInstaller) {
            Copy-Item -LiteralPath $enterpriseInstaller -Destination $publicInstaller -Force
            Write-Host "Public installer alias generated: $publicInstaller" -ForegroundColor Green
        }
    } else {
        Write-Warning "Inno Setup compilation failed with code $LASTEXITCODE."
    }
} else {
    Write-Warning "Inno Setup compiler not found on system PATH. Onedir build is ready in $DistDir\Stepwise."
}

Write-Host "=========================================" -ForegroundColor Green
Write-Host " Build Process Completed Successfully!   " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
