# Execute the real entry point in a disposable repository with fake tool/signature providers.
$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
. "$sourceRoot\scripts\release_helpers.ps1"
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('stepwise-orchestration-' + [guid]::NewGuid().ToString('N'))
$originalLocation = Get-Location
$script:checks = 0
$global:fixtureSignCalls = @()
$global:fixtureFailInstaller = $false
function Assert-True($Condition, [string]$Message) { if (-not $Condition) { throw $Message }; $script:checks++ }
function git {
    if ($args[0] -eq 'rev-parse') { $global:LASTEXITCODE = 0; return 'fixture-commit' }
    if ($args[0] -eq 'status') { $global:LASTEXITCODE = 0; return }
    throw 'Unexpected Git command in fixture.'
}
function Get-Item {
    param([string]$Path, [string]$LiteralPath, [object]$ErrorAction)
    if ($Path -like 'Cert:*') {
        return [pscustomobject]@{ HasPrivateKey=$true; NotAfter=(Get-Date).AddDays(1); Subject='Fixture signer' }
    }
    Microsoft.PowerShell.Management\Get-Item @PSBoundParameters
}
function Get-AuthenticodeSignature([string]$LiteralPath) {
    [pscustomobject]@{ Status=$(if ([IO.File]::ReadAllText($LiteralPath).EndsWith('|signed')) { 'Valid' } else { 'NotSigned' });
        SignerCertificate=[pscustomobject]@{ Thumbprint='fixture-thumbprint' };
        TimeStamperCertificate=[pscustomobject]@{ Subject='Fixture timestamp' } }
}
try {
    foreach ($directory in @('scripts','installer','release','build\unsigned\run\dist\Stepwise')) {
        [IO.Directory]::CreateDirectory((Join-Path $fixture $directory)) | Out-Null
    }
    foreach ($name in @('sign.ps1','release_helpers.ps1')) { Copy-Item -LiteralPath "$sourceRoot\scripts\$name" -Destination "$fixture\scripts\$name" }
    [IO.File]::WriteAllText("$fixture\pyproject.toml", 'version = "9.9.9"')
    [IO.File]::WriteAllText("$fixture\installer\setup.iss", 'Fixture compiler does not read Inno source.')
    [IO.File]::WriteAllText("$fixture\release\old-official.exe", 'protected old release')
    [IO.File]::WriteAllText("$fixture\release\build-manifest.json", 'protected old metadata')
    $build = "$fixture\build\unsigned\run"
    [IO.File]::WriteAllText("$build\dist\Stepwise\Stepwise.exe", 'fixture unsigned app')
    [IO.File]::WriteAllText("$build\test-results.txt", 'fixture test success evidence; not actual application tests')
    Write-ReleaseJson "$build\build-input.json" ([ordered]@{
        product_id='App06_Stepwise'; version='9.9.9'; git_commit='fixture-commit'; source_dirty=$false
        built_at_utc='fixture-time'; bundle=@(Get-BundleInventory "$build\dist\Stepwise")
        tests_passed=$true; test_commands=@('fixture mocks'); test_results_sha256=(Get-FileHash "$build\test-results.txt").Hash.ToLowerInvariant()
    })
    $signer = @'
$path = $args[-1]
$global:fixtureSignCalls += Split-Path -Leaf $path
[IO.File]::AppendAllText($path, '|signed')
$global:LASTEXITCODE = 0
'@
    [IO.File]::WriteAllText("$fixture\signer.ps1", $signer)
    $compiler = @'
if ($global:fixtureFailInstaller) { $global:LASTEXITCODE = 1; return }
$output = ($args | Where-Object { $_ -like '/DMyAppOutputDir=*' }).Substring(17)
$source = ($args | Where-Object { $_ -like '/DMyAppSourceDir=*' }).Substring(17)
if (-not ([IO.File]::ReadAllText((Join-Path $source 'Stepwise.exe'))).EndsWith('|signed')) { throw 'Installer input was not signed first.' }
[IO.File]::WriteAllText((Join-Path $output 'App06_Stepwise_Setup_v9.9.9.exe'), 'fixture unsigned installer')
$global:LASTEXITCODE = 0
'@
    [IO.File]::WriteAllText("$fixture\compiler.ps1", $compiler)
    & "$fixture\scripts\sign.ps1" -BuildRoot $build -SignToolPath "$fixture\signer.ps1" -CertificateThumbprint 'fixture-thumbprint' -InnoCompilerPath "$fixture\compiler.ps1"
    Assert-True (($global:fixtureSignCalls -join ',') -eq 'Stepwise.exe,App06_Stepwise_Setup_v9.9.9.exe') 'Expected app-first and exactly one installer signing call.'
    $release = "$fixture\release"
    $stagedInstaller = @(Get-ChildItem -LiteralPath "$fixture\build\release-staging" -Recurse -File -Filter 'App06_Stepwise_Setup_v9.9.9.exe')
    Assert-True ($stagedInstaller.Count -eq 1) 'Unexpected staging installer count.'
    Assert-True ((Get-FileHash -LiteralPath "$release\App06_Stepwise_Setup_v9.9.9.exe").Hash -eq (Get-FileHash -LiteralPath $stagedInstaller[0].FullName).Hash) 'Promoted installer differs.'
    Assert-True (-not (Test-Path -LiteralPath "$release\Stepwise-Setup.v9.9.9.exe")) 'Unexpected installer alias created.'
    Assert-True (-not (Test-Path -LiteralPath "$release\Stepwise.v9.9.9.zip")) 'Unexpected portable ZIP created.'
    Assert-True ([IO.File]::ReadAllText("$build\dist\Stepwise\Stepwise.exe") -eq 'fixture unsigned app') 'Unsigned build modified.'
    Assert-True ([IO.File]::ReadAllText("$release\old-official.exe") -eq 'protected old release') 'Old official artifact modified.'
    Assert-True ([IO.File]::ReadAllText("$release\build-manifest.json") -eq 'protected old metadata') 'Old generic metadata modified.'
    $beforeFailure = @(Get-BundleInventory $release)
    $global:fixtureFailInstaller = $true
    $failed = $false
    try { & "$fixture\scripts\sign.ps1" -BuildRoot $build -SignToolPath "$fixture\signer.ps1" -CertificateThumbprint 'fixture-thumbprint' -InnoCompilerPath "$fixture\compiler.ps1" } catch { $failed=$true }
    Assert-True $failed 'Compiler failure not propagated.'
    Assert-BundleInventory $release $beforeFailure
    $script:checks++
    $beforeRejectCalls = $global:fixtureSignCalls.Count
    $provenancePath = "$build\build-input.json"
    $provenanceText = [IO.File]::ReadAllText($provenancePath)
    $provenance = $provenanceText | ConvertFrom-Json
    foreach ($badCase in @('tests','commit')) {
        $provenance = $provenanceText | ConvertFrom-Json
        if ($badCase -eq 'tests') { $provenance.tests_passed = $false } else { $provenance.git_commit='wrong-commit' }
        Write-ReleaseJson $provenancePath $provenance
        $failed=$false
        try { & "$fixture\scripts\sign.ps1" -BuildRoot $build -SignToolPath "$fixture\signer.ps1" -CertificateThumbprint 'fixture-thumbprint' -InnoCompilerPath "$fixture\compiler.ps1" } catch { $failed=$true }
        Assert-True $failed "Invalid provenance accepted: $badCase"
        Assert-True ($global:fixtureSignCalls.Count -eq $beforeRejectCalls) 'Signing was invoked before provenance rejection.'
    }
    [IO.File]::WriteAllText($provenancePath,$provenanceText)
    [IO.File]::AppendAllText("$build\test-results.txt", 'tampered test evidence')
    $failed=$false
    try { & "$fixture\scripts\sign.ps1" -BuildRoot $build -SignToolPath "$fixture\signer.ps1" -CertificateThumbprint 'fixture-thumbprint' -InnoCompilerPath "$fixture\compiler.ps1" } catch { $failed=$true }
    Assert-True $failed 'Modified test evidence accepted.'
    Assert-True ($global:fixtureSignCalls.Count -eq $beforeRejectCalls) 'Signing invoked for modified test evidence.'
    Write-Output "PASS: $script:checks real-orchestration fixture assertions; fake signer/compiler, no signing or publication."
} finally {
    Set-Location -LiteralPath $originalLocation.Path
    $absolute = [IO.Path]::GetFullPath($fixture)
    $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $absolute.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Leaf $absolute) -notlike 'stepwise-orchestration-*') { throw 'Unsafe fixture cleanup target.' }
    Remove-Item -LiteralPath $absolute -Recurse -Force
    Remove-Variable fixtureSignCalls,fixtureFailInstaller -Scope Global -ErrorAction SilentlyContinue
}
