# Explicit signing of a clean provenance-checked build; publishing is opt-in.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BuildRoot,
    [string]$SignToolPath = $env:SIGNTOOL_PATH,
    [string]$CertificateThumbprint = $env:STEPWISE_SIGNING_THUMBPRINT,
    [string]$InnoCompilerPath,
    [switch]$Publish
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location -LiteralPath $projectRoot
. "$PSScriptRoot\release_helpers.ps1"
function Find-SuiteSignTool {
    param([string]$RequestedPath)
    if ($RequestedPath) {
        if (-not (Test-Path -LiteralPath $RequestedPath -PathType Leaf)) {
            throw 'The specified SignTool path does not exist.'
        }
        return (Resolve-Path -LiteralPath $RequestedPath).Path
    }
    $candidates = @()
    $onPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($onPath) { $candidates += $onPath.Source }
    $candidates += Join-Path $projectRoot 'tools\signtool\signtool.exe'
    foreach ($sdkRoot in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
        if (-not $sdkRoot) { continue }
        $sdkBin = Join-Path $sdkRoot 'Windows Kits\10\bin'
        $versions = @(Get-ChildItem -LiteralPath $sdkBin -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' } |
            Sort-Object { [version]$_.Name } -Descending)
        foreach ($directory in $versions) {
            $candidates += Join-Path $directory.FullName 'x64\signtool.exe'
        }
        $candidates += Join-Path $sdkBin 'x64\signtool.exe'
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw 'Provide -SignToolPath, SIGNTOOL_PATH, SignTool on PATH, or install the Windows SDK.'
}
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
$signtool = Find-SuiteSignTool -RequestedPath $SignToolPath
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
    & $signtool sign /sha1 $CertificateThumbprint /fd sha256 /tr http://timestamp.digicert.com /td sha256 $Path
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $(Split-Path -Leaf $Path). Official release files were not changed." }
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
