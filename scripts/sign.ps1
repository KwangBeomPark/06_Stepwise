# Stepwise One-Click Digital Signing & GitHub Release Script
# Run in an ELEVATED (Administrator) PowerShell window:
# powershell -ExecutionPolicy Bypass -File scripts\sign.ps1

$ErrorActionPreference = 'Stop'
$projectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location -LiteralPath $projectRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Stepwise Digital Signing Pipeline " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Administrator check
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script MUST be run in an Administrator PowerShell window. Please right-click PowerShell -> 'Run as Administrator'."
    exit 1
}

# 2. Ensure Smart Card Services are active
Write-Host "[1/6] Ensuring Smart Card services are active..." -ForegroundColor Yellow
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

# 4. Sign main application binary
$signtoolPaths = @(
    "$projectRoot\release\build\signtool\signtool.exe",
    "C:\Users\parkk\.codex\worktrees\antigravity-aggregation-review\04_DataRefinery\release\build\windows-sdk-buildtools-10.0.28000.2705\package\bin\10.0.28000.0\x64\signtool.exe",
    (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
)
$signtool = $signtoolPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $signtool) {
    Write-Error "SignTool not found."
    exit 1
}

$appExe = "$projectRoot\dist\Stepwise\Stepwise.exe"
if (-not (Test-Path $appExe)) {
    Write-Error "Stepwise.exe not found at $appExe. Run scripts\build.ps1 first."
    exit 1
}

Write-Host "[2/6] Digitally signing Stepwise.exe..." -ForegroundColor Yellow
& $signtool sign /sha1 $thumbprint /fd sha256 /tr http://timestamp.digicert.com /td sha256 /v $appExe
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Primary timestamp failed, retrying with Certum timestamp server..."
    & $signtool sign /sha1 $thumbprint /fd sha256 /tr http://time.certum.pl /td sha256 /v $appExe
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to sign Stepwise.exe"
        exit $LASTEXITCODE
    }
}
Write-Host "Stepwise.exe signed successfully!" -ForegroundColor Green

# 5. Compile Inno Setup installer
Write-Host "[3/6] Compiling installer with Inno Setup..." -ForegroundColor Yellow
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

& $iscc "$projectRoot\installer\stepwise.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup compilation failed with code $LASTEXITCODE"
    exit $LASTEXITCODE
}

# 6. Sign installer executable
$setupFiles = Get-ChildItem "$projectRoot\release\dist\*Stepwise-Setup*.exe" | Sort-Object LastWriteTime -Descending
if (-not $setupFiles) {
    Write-Error "Installer executable not found in release\dist"
    exit 1
}
$installerExe = $setupFiles[0].FullName

Write-Host "[4/6] Digitally signing installer $(Split-Path -Leaf $installerExe)..." -ForegroundColor Yellow
& $signtool sign /sha1 $thumbprint /fd sha256 /tr http://timestamp.digicert.com /td sha256 /v $installerExe
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Primary timestamp failed, retrying with Certum timestamp server..."
    & $signtool sign /sha1 $thumbprint /fd sha256 /tr http://time.certum.pl /td sha256 /v $installerExe
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to sign installer"
        exit $LASTEXITCODE
    }
}
Write-Host "Installer signed successfully!" -ForegroundColor Green

# 7. Verify signatures
Write-Host "[5/6] Verifying signatures..." -ForegroundColor Yellow
foreach ($bin in @($appExe, $installerExe)) {
    $sig = Get-AuthenticodeSignature -LiteralPath $bin
    if ($sig.Status -ne "Valid") {
        Write-Error "Signature invalid for: $bin ($($sig.StatusMessage))"
        exit 1
    }
    Write-Host "Verified $($sig.Status): $(Split-Path -Leaf $bin) (Timestamped: $($sig.TimeStamperCertificate.Subject))" -ForegroundColor Green
}

# 8. Upload / Create on GitHub Release
$fileName = Split-Path -Leaf $installerExe
$versionMatch = [regex]::Match($fileName, "(?:.*Stepwise-Setup[_-]v?)([0-9\.]+)\.exe")
if (-not $versionMatch.Success) {
    $versionMatch = [regex]::Match($fileName, "([0-9]+\.[0-9]+\.[0-9]+)")
}

if ($versionMatch.Success) {
    $ver = $versionMatch.Groups[1].Value
    $tag = "v$ver"
    Write-Host "[6/6] Publishing signed installer to GitHub Release $tag..." -ForegroundColor Yellow

    $null = & gh release view $tag 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Release $tag does not exist. Creating new release..." -ForegroundColor Cyan
        & gh release create $tag $installerExe --title "v$ver - Stepwise Release" --generate-notes
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Successfully created GitHub Release $tag and uploaded installer!" -ForegroundColor Green
        } else {
            Write-Warning "Failed to create GitHub Release $tag. Check gh auth status or permissions."
        }
    } else {
        Write-Host "Release $tag exists. Uploading/updating asset..." -ForegroundColor Cyan
        & gh release upload $tag $installerExe --clobber
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Successfully uploaded signed installer to GitHub Release $tag!" -ForegroundColor Green
        } else {
            Write-Warning "Failed to upload to GitHub Release. Check gh auth status."
        }
    }
} else {
    Write-Warning "Could not extract version from installer file name: $fileName"
}

Write-Host "=========================================" -ForegroundColor Green
Write-Host " Signing & Release Completed 100%! " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
