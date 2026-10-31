# Explicit signing of a clean provenance-checked build; publishing is opt-in.
[CmdletBinding()]
param(
    [string]$BuildRoot,
    [string]$SignToolPath = $env:SIGNTOOL_PATH,
    [ValidateSet('x64','x86','arm64')][string]$SignToolArchitecture = 'x64',
    [string]$CertificateThumbprint = $env:STEPWISE_SIGNING_THUMBPRINT,
    [string]$InnoCompilerPath,
    [switch]$Diagnose,
    [switch]$Publish
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location -LiteralPath $projectRoot
. "$PSScriptRoot\release_helpers.ps1"
function Get-SuiteToolArchitecture([string]$Path) {
    # Read the PE header: the host PowerShell bitness does not determine SignTool bitness.
    if ([IO.Path]::GetExtension($Path) -eq '.ps1') { return 'script' }
    $stream = [IO.File]::OpenRead($Path)
    $reader = New-Object IO.BinaryReader($stream)
    try {
        if ($reader.ReadUInt16() -ne 0x5a4d) { throw "Not a PE executable: $Path" }
        $stream.Position = 0x3c
        $offset = $reader.ReadInt32()
        if ($offset -lt 0 -or $offset -gt ($stream.Length - 6)) { throw "Invalid PE header: $Path" }
        $stream.Position = $offset
        if ($reader.ReadUInt32() -ne 0x4550) { throw "Invalid PE signature: $Path" }
        switch ($reader.ReadUInt16()) {
            0x8664 { return 'x64' }
            0x014c { return 'x86' }
            0xaa64 { return 'arm64' }
            default { throw "Unsupported PE architecture: $Path" }
        }
    } finally { $reader.Dispose() }
}
function Find-SuiteSignTool {
    param([string]$RequestedPath, [string]$Architecture = 'x64')
    if ($RequestedPath) {
        if (-not (Test-Path -LiteralPath $RequestedPath -PathType Leaf)) {
            throw 'The specified SignTool path does not exist.'
        }
        return (Resolve-Path -LiteralPath $RequestedPath).Path
    }
    $candidates = @()
    # Prefer an intact SDK installation to an arbitrary PATH entry or copied tool.
    foreach ($sdkRoot in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
        if (-not $sdkRoot) { continue }
        $sdkBin = Join-Path $sdkRoot 'Windows Kits\10\bin'
        $versions = @(Get-ChildItem -LiteralPath $sdkBin -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' } |
            Sort-Object { [version]$_.Name } -Descending)
        foreach ($directory in $versions) {
            $candidates += Join-Path $directory.FullName "$Architecture\signtool.exe"
        }
        $candidates += Join-Path $sdkBin "$Architecture\signtool.exe"
    }
    $candidates += Join-Path $projectRoot 'tools\signtool\signtool.exe'
    $onPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($onPath) { $candidates += $onPath.Source }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            if ((Get-SuiteToolArchitecture $candidate) -eq $Architecture) {
                return (Resolve-Path -LiteralPath $candidate).Path
            }
        }
    }
    throw "No $Architecture SignTool found. Provide -SignToolPath / SIGNTOOL_PATH or install the Windows SDK with signing tools."
}
function Write-SuiteSignToolInfo([string]$Path) {
    $architecture = Get-SuiteToolArchitecture $Path
    $version = (Get-Item -LiteralPath $Path).VersionInfo.ProductVersion
    Write-Host "SignTool: $Path"
    Write-Host "SignTool architecture: $architecture; product version: $version; PowerShell 64-bit: $([Environment]::Is64BitProcess)"
    Write-Host 'Certificate store: CurrentUser\My (no /sm). HasPrivateKey is metadata, not proof of usable key access.'
}
if ($Diagnose) {
    if (-not $CertificateThumbprint) { throw 'Provide -CertificateThumbprint or STEPWISE_SIGNING_THUMBPRINT.' }
    try {
        $diagnosticTool = Find-SuiteSignTool -RequestedPath $SignToolPath -Architecture $SignToolArchitecture
        Write-SuiteSignToolInfo $diagnosticTool
    } catch { Write-Warning $_.Exception.Message }
    # Silent diagnostics only: no store repair, signing, build, or publication.
    $certutilPaths = @("$env:windir\System32\certutil.exe")
    if ([Environment]::Is64BitOperatingSystem) {
        if (-not [Environment]::Is64BitProcess) { $certutilPaths[0] = "$env:windir\Sysnative\certutil.exe" }
        $certutilPaths += "$env:windir\SysWOW64\certutil.exe"
    }
    foreach ($certutil in $certutilPaths) {
        Write-Host "=== Certificate/key association: $certutil ==="
        & $certutil -silent -user -v -store My $CertificateThumbprint
        Write-Host "certutil store exit code: $LASTEXITCODE (inspect key verification messages even when zero)"
        Write-Host "=== Registered providers: $certutil ==="
        & $certutil -silent -csplist
        Write-Host "certutil csplist exit code: $LASTEXITCODE (an unrelated provider can also fail)"
    }
    Write-Host 'Diagnostics complete; key signability has not been tested. See docs/SIGNING_TROUBLESHOOTING.md.'
    return
}
if (-not $BuildRoot) { throw 'Provide -BuildRoot for signing, or use -Diagnose for read-only diagnostics.' }
$Version = ([regex]::Match((Get-Content pyproject.toml -Raw), '(?m)^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')).Groups[1].Value
if (-not $Version) { throw 'A valid project version is required.' }
$Commit = & git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve source commit.' }
$sourceStatus = @(& git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $sourceStatus.Count) { throw 'Commit all source changes and rebuild before release signing.' }
$BuildRoot = (Resolve-Path -LiteralPath $BuildRoot).Path
$allowed = [IO.Path]::GetFullPath((Join-Path $projectRoot 'build\unsigned')).TrimEnd('\') + '\'
if (-not $BuildRoot.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw 'BuildRoot must be an owned unsigned build directory.' }
$ancestor = $BuildRoot
while ($ancestor.Length -gt $projectRoot.Length) {
    if ((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Build path must not contain reparse points.' }
    $ancestor = Split-Path -Parent $ancestor
}
$inputManifest = Get-Content -LiteralPath "$BuildRoot\build-input.json" -Raw | ConvertFrom-Json
if ($inputManifest.product_id -ne 'App06_Stepwise' -or $inputManifest.version -ne $Version -or $inputManifest.git_commit -ne $Commit -or $inputManifest.source_dirty -ne $false -or $inputManifest.tests_passed -ne $true) { throw 'Build provenance does not match tested clean current source.' }
if ((Get-FileHash -LiteralPath "$BuildRoot\test-results.txt" -Algorithm SHA256).Hash.ToLowerInvariant() -cne $inputManifest.test_results_sha256) { throw 'Build test evidence changed or is missing.' }
$unsignedBundle = Join-Path $BuildRoot 'dist\Stepwise'
Assert-BundleInventory $unsignedBundle $inputManifest.bundle
if (-not $CertificateThumbprint) { throw 'Provide -CertificateThumbprint or STEPWISE_SIGNING_THUMBPRINT.' }
$signtool = Find-SuiteSignTool -RequestedPath $SignToolPath -Architecture $SignToolArchitecture
Write-SuiteSignToolInfo $signtool
$cert = Get-Item "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction Stop
if (-not $cert.HasPrivateKey) { throw 'Signing certificate has no available private key.' }
if ($cert.NotAfter -lt (Get-Date)) { throw 'Signing certificate expired.' }
if (-not $InnoCompilerPath) {
    $foundCompiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($foundCompiler) { $InnoCompilerPath = $foundCompiler.Source }
    foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles, (Join-Path $env:LOCALAPPDATA 'Programs'))) {
        if ($InnoCompilerPath) { break }
        foreach ($major in @(7,6)) {
            $candidate = Join-Path $base "Inno Setup $major\ISCC.exe"
            if (Test-Path -LiteralPath $candidate) { $InnoCompilerPath = $candidate; break }
        }
    }
}
if (-not $InnoCompilerPath -or -not (Test-Path -LiteralPath $InnoCompilerPath -PathType Leaf)) { throw 'Inno Setup compiler is required.' }
$runRoot = Join-Path $projectRoot ('build\release-staging\' + [guid]::NewGuid().ToString('N'))
Assert-OwnedBuildPath $runRoot $projectRoot
$bundle = Join-Path $runRoot 'Stepwise'
$stage = Join-Path $runRoot 'artifacts'
[IO.Directory]::CreateDirectory($stage) | Out-Null
Copy-Item -LiteralPath $unsignedBundle -Destination $bundle -Recurse
Assert-BundleInventory $bundle $inputManifest.bundle
function Invoke-SignBinary([string]$Path) {
    & $signtool sign /v /debug /s My /sha1 $CertificateThumbprint /fd sha256 /tr http://timestamp.digicert.com /td sha256 $Path
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed: $(Split-Path -Leaf $Path) (exit $LASTEXITCODE; tool: $signtool). Official release files were not changed. Run scripts\sign.ps1 -Diagnose -CertificateThumbprint $CertificateThumbprint and inspect provider/key association and architecture. See docs/SIGNING_TROUBLESHOOTING.md."
    }
    Assert-ReleaseSignature $Path $CertificateThumbprint
}
# Only the explicitly invoked signing pipeline accesses the user's signing session.
Invoke-SignBinary (Join-Path $bundle 'Stepwise.exe')
& $InnoCompilerPath "/DMyAppVersion=$Version" "/DMyAppSourceDir=$bundle" "/DMyAppOutputDir=$stage" "$projectRoot\installer\setup.iss"
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed; official release files were not changed.' }
$enterprise = Join-Path $stage "App06_Stepwise_Setup_v$Version.exe"
Invoke-SignBinary $enterprise
$names = @((Split-Path -Leaf $enterprise))
$artifacts = @($names | ForEach-Object {
    [ordered]@{ name = $_; sha256 = (Get-FileHash -LiteralPath (Join-Path $stage $_) -Algorithm SHA256).Hash.ToLowerInvariant() }
})
Write-ReleaseJson (Join-Path $stage "build-manifest.v$Version.json") ([ordered]@{
    product_id = 'App06_Stepwise'; app_name = 'Stepwise'; version = $Version
    git_commit = $Commit; built_at_utc = $inputManifest.built_at_utc
    verified_at_utc = [DateTime]::UtcNow.ToString('o'); source_dirty = $false
    certificate_thumbprint = $CertificateThumbprint; signer_subject = $cert.Subject
    signature_policy = 'Valid expected-signer Authenticode with timestamp'
    tests_passed = $inputManifest.tests_passed; test_commands = $inputManifest.test_commands
    test_results_sha256 = $inputManifest.test_results_sha256
    signed_bundle = @(Get-BundleInventory $bundle); artifacts = $artifacts
})
[IO.File]::WriteAllLines((Join-Path $stage "SHA256SUMS.v$Version.txt"), @($artifacts | ForEach-Object { "$($_.sha256)  $($_.name)" }), (New-Object Text.UTF8Encoding($false)))
$releaseNames = @(Assert-ReleaseArtifacts $stage $Version $Commit $CertificateThumbprint)
$finalCommit = & git rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $finalCommit -ne $Commit) { throw 'Source commit changed while signing; release promotion refused.' }
$finalStatus = @(& git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $finalStatus.Count) { throw 'Source changed while signing; release promotion refused.' }
Publish-LocalRelease $stage (Join-Path $projectRoot 'release') $releaseNames
Write-Output "Verified local release prepared: $Version. Existing versions and generic metadata were preserved."
if ($Publish) {
    Publish-GitHubRelease (Join-Path $projectRoot 'release') $releaseNames "v$Version" $Commit (Join-Path $runRoot 'remote-verification')
} else { Write-Output 'GitHub publication was not requested.' }
