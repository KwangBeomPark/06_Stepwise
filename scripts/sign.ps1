# Stepwise One-Click Digital Signing & GitHub Release Pipeline (PL Suite App06)
# Run in an ELEVATED (Administrator) PowerShell window:
# powershell -ExecutionPolicy Bypass -File scripts\sign.ps1

$ErrorActionPreference = 'Stop'
$projectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location -LiteralPath $projectRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Stepwise Digital Signing Pipeline       " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 0. Administrator check
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script MUST be run in an Administrator PowerShell window. Please right-click PowerShell -> 'Run as Administrator'."
    exit 1
}

# 1. Resolve Version from pyproject.toml
$pyprojectContent = Get-Content "$projectRoot\pyproject.toml" -Raw
$versionMatch = [regex]::Match($pyprojectContent, 'version\s*=\s*["'']([^"'']+)["'']')
if ($versionMatch.Success) {
    $Version = $versionMatch.Groups[1].Value
} else {
    $Version = "0.2.1"
}
$tag = "v$Version"
Write-Host "Target Version: $Version (Tag: $tag)" -ForegroundColor Yellow

# 2. Ensure Smart Card Services are active
Write-Host "[1/7] Ensuring Smart Card services are active..." -ForegroundColor Yellow
Start-Service SCardSvr, CertPropSvc, ScDeviceEnum -ErrorAction SilentlyContinue

# 3. Locate certificate
$thumbprint = "E9C72CF5090840A1805296525D56BE680622A7FD"
$cert = Get-Item "Cert:\CurrentUser\My\$thumbprint" -ErrorAction SilentlyContinue
if (-not $cert) {
    $cert = Get-Item "Cert:\LocalMachine\My\$thumbprint" -ErrorAction SilentlyContinue
}
if (-not $cert) {
    Write-Error "Code signing certificate [$thumbprint] not found in Cert: store. Please ensure SimplySign is logged in."
    exit 1
}
Write-Host "Certificate found: $($cert.Subject)" -ForegroundColor Green

# 4. Locate SignTool
$signtoolPaths = @(
    "$projectRoot\release\build\signtool\signtool.exe",
    "C:\Users\parkk\.codex\worktrees\antigravity-aggregation-review\04_DataRefinery\release\build\windows-sdk-buildtools-10.0.28000.2705\package\bin\10.0.28000.0\x64\signtool.exe",
    (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
)
$signtool = $signtoolPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $signtool) {
    Write-Error "SignTool not found on system."
    exit 1
}

function Invoke-SignBinary {
    param([string]$FilePath)
    Write-Host "Signing $(Split-Path -Leaf $FilePath)..." -ForegroundColor Cyan
    & $signtool sign /sha1 $thumbprint /fd sha256 /tr http://timestamp.digicert.com /td sha256 /v $FilePath
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Primary timestamp server failed. Retrying with Certum timestamp..."
        & $signtool sign /sha1 $thumbprint /fd sha256 /tr http://time.certum.pl /td sha256 /v $FilePath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to sign $FilePath"
        }
    }
}

# 5. Sign main application binary
$appExe = "$projectRoot\dist\Stepwise\Stepwise.exe"
if (-not (Test-Path $appExe)) {
    Write-Error "Stepwise.exe not found at $appExe. Run scripts\build.ps1 first."
    exit 1
}
Write-Host "[2/7] Digitally signing Stepwise.exe..." -ForegroundColor Yellow
Invoke-SignBinary -FilePath $appExe

# 6. Compile Inno Setup installer
Write-Host "[3/7] Compiling installer with Inno Setup..." -ForegroundColor Yellow
$isccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
)
$iscc = $isccPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
    Write-Error "Inno Setup compiler (ISCC.exe) not found."
    exit 1
}

$issFile = "$projectRoot\installer\setup.iss"
if (!(Test-Path $issFile)) { $issFile = "$projectRoot\installer\stepwise.iss" }

& $iscc "/DMyAppVersion=$Version" $issFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup compilation failed with code $LASTEXITCODE"
    exit $LASTEXITCODE
}

# 7. Generate and Sign Dual Naming Installers
Write-Host "[4/7] Signing Dual Naming Installers..." -ForegroundColor Yellow
$releaseDistDir = "$projectRoot\release\dist"
$enterpriseInstaller = "$releaseDistDir\App06_Stepwise-Setup_v$Version.exe"
$publicInstaller = "$releaseDistDir\Stepwise-Setup.v$Version.exe"

if (Test-Path $enterpriseInstaller) {
    Invoke-SignBinary -FilePath $enterpriseInstaller
    Copy-Item -LiteralPath $enterpriseInstaller -Destination $publicInstaller -Force
    Invoke-SignBinary -FilePath $publicInstaller
} else {
    Write-Error "Installer executable not found: $enterpriseInstaller"
    exit 1
}

# 8. Stage to release/ root and generate checksums & manifest
Write-Host "[5/7] Staging official release artifacts to release/..." -ForegroundColor Yellow
$releaseRootDir = "$projectRoot\release"
if (-not (Test-Path $releaseRootDir)) { New-Item -ItemType Directory -Force $releaseRootDir | Out-Null }

$artifacts = @(
    $enterpriseInstaller,
    $publicInstaller
)
$portableZip = "$releaseDistDir\Stepwise.v$Version.zip"
if (Test-Path $portableZip) {
    $artifacts += $portableZip
}

$stagedFiles = @()
foreach ($art in $artifacts) {
    $dest = "$releaseRootDir\$(Split-Path -Leaf $art)"
    Copy-Item -LiteralPath $art -Destination $dest -Force
    $stagedFiles += $dest
}

# Generate SHA256SUMS.txt (UTF-8 No-BOM)
$checksumLines = @()
foreach ($file in $stagedFiles) {
    $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    $leaf = Split-Path -Leaf $file
    $checksumLines += "$hash  $leaf"
}
$checksumPath = "$releaseRootDir\SHA256SUMS.txt"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($checksumPath, $checksumLines, $utf8NoBom)
Write-Host "Generated: SHA256SUMS.txt" -ForegroundColor Green

# Generate build-manifest.json
$gitCommit = (& git rev-parse HEAD 2>$null)
if (-not $gitCommit) { $gitCommit = "unknown" }

$manifest = [ordered]@{
    product_id = "App06_Stepwise"
    app_name = "Stepwise"
    version = $Version
    git_commit = $gitCommit
    build_time = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")
    certificate_thumbprint = $thumbprint
    signer_subject = $cert.Subject
    artifacts = @($stagedFiles | ForEach-Object { Split-Path -Leaf $_ })
}
$manifestPath = "$releaseRootDir\build-manifest.json"
$manifestJson = $manifest | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($manifestPath, $manifestJson, $utf8NoBom)
Write-Host "Generated: build-manifest.json" -ForegroundColor Green

# 9. Verify Signatures
Write-Host "[6/7] Verifying all Authenticode signatures..." -ForegroundColor Yellow
foreach ($bin in @($appExe, $enterpriseInstaller, $publicInstaller)) {
    $sig = Get-AuthenticodeSignature -LiteralPath $bin
    if ($sig.Status -ne "Valid") {
        Write-Error "Signature invalid for: $bin ($($sig.StatusMessage))"
        exit 1
    }
    Write-Host "Verified Valid: $(Split-Path -Leaf $bin)" -ForegroundColor Green
}

# 10. Publish to GitHub Release
Write-Host "[7/7] Publishing artifacts to GitHub Release $tag..." -ForegroundColor Yellow
$uploadFiles = @($stagedFiles) + @($checksumPath, $manifestPath)

$releaseList = & gh release list --limit 50 2>$null
$releaseExists = ($releaseList -match "\b$([regex]::Escape($tag))\b")

if (-not $releaseExists) {
    Write-Host "Creating GitHub Release $tag..." -ForegroundColor Cyan
    & gh release create $tag @uploadFiles --title "v$Version - Stepwise Release" --generate-notes
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Successfully created GitHub Release $tag!" -ForegroundColor Green
    } else {
        Write-Warning "Failed to create GitHub Release. Check gh auth status."
    }
} else {
    Write-Host "Updating existing GitHub Release $tag..." -ForegroundColor Cyan
    & gh release upload $tag @uploadFiles --clobber
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Successfully uploaded all assets to GitHub Release $tag!" -ForegroundColor Green
    } else {
        Write-Warning "Failed to upload to GitHub Release. Check gh auth status."
    }
}

Write-Host "=========================================" -ForegroundColor Green
Write-Host " PL Suite App06 Release Complete 100%!   " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
