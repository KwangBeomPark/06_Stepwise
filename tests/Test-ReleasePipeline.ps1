# Isolated fixture tests. Signatures are mocked; no certificate, service, or network use.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\scripts\release_helpers.ps1"
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('stepwise-release-test-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($fixture) | Out-Null
$script:checks = 0
function Assert-True($Condition, [string]$Message) { if (-not $Condition) { throw $Message }; $script:checks++ }
function Assert-Fails([scriptblock]$Action, [string]$Message) {
    $failed = $false
    try { & $Action | Out-Null } catch { $failed = $true }
    Assert-True $failed $Message
}
function Get-AuthenticodeSignature([string]$LiteralPath) {
    $content = [IO.File]::ReadAllText($LiteralPath)
    [pscustomobject]@{ Status = $(if ($content -eq 'signed') { 'Valid' } else { 'NotSigned' });
        SignerCertificate = [pscustomobject]@{ Thumbprint = 'test-thumbprint' };
        TimeStamperCertificate = [pscustomobject]@{ Subject = 'fixture timestamp' } }
}
function New-Stage([string]$Name) {
    $stage = Join-Path $fixture $Name
    [IO.Directory]::CreateDirectory($stage) | Out-Null
    $names = @('App06_Stepwise_Setup_v9.9.9.exe')
    foreach ($name in $names) { [IO.File]::WriteAllText((Join-Path $stage $name), 'signed') }
    $artifacts = @($names | ForEach-Object { [ordered]@{ name = $_; sha256 = (Get-FileHash -LiteralPath (Join-Path $stage $_)).Hash.ToLowerInvariant() } })
    Write-ReleaseJson (Join-Path $stage 'build-manifest.v9.9.9.json') ([ordered]@{
        product_id='App06_Stepwise'; version='9.9.9'; git_commit='fixture-commit'; certificate_thumbprint='test-thumbprint'; artifacts=$artifacts
    })
    [IO.File]::WriteAllLines((Join-Path $stage 'SHA256SUMS.v9.9.9.txt'), @($artifacts | ForEach-Object { "$($_.sha256)  $($_.name)" }))
    return $stage
}
function gh {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'api') {
        if ($args[1] -like '*/git/ref/tags/*') {
            return (@{ object=@{ type='commit'; sha=$script:remoteCommit } } | ConvertTo-Json -Compress)
        }
        return ('[[{"tag_name":"v9.9.9","assets":[' + (($script:remoteFiles.Keys | ForEach-Object { '{"name":"' + $_ + '"}' }) -join ',') + ']}]]')
    }
    if ($args[0] -eq 'release' -and $args[1] -eq 'download') {
        $name = $args[4]
        $directory = $args[6]
        [IO.File]::WriteAllText((Join-Path $directory $name),$script:remoteFiles[$name])
        return
    }
    if ($args[0] -eq 'release' -and $args[1] -eq 'upload') {
        foreach ($path in $args[3..($args.Count-1)]) {
            $name = Split-Path -Leaf $path
            $script:uploaded += $name
            $script:remoteFiles[$name] = [IO.File]::ReadAllText($path)
        }
        return
    }
    throw 'Unexpected GitHub operation in fixture.'
}
try {
    $bundle = Join-Path $fixture 'bundle'
    [IO.Directory]::CreateDirectory($bundle) | Out-Null
    [IO.File]::WriteAllText((Join-Path $bundle 'Stepwise.exe'), 'signed')
    $inventory = @(Get-BundleInventory $bundle)
    Assert-BundleInventory $bundle $inventory
    Assert-True ($inventory.Count -eq 1) 'Bundle inventory failed.'
    [IO.File]::WriteAllText((Join-Path $bundle 'Stepwise.exe'), 'unsigned')
    Assert-Fails { Assert-BundleInventory $bundle $inventory } 'Modified unsigned input accepted.'
    Assert-Fails { Assert-ReleaseSignature (Join-Path $bundle 'Stepwise.exe') 'test-thumbprint' } 'Unsigned executable accepted.'
    [IO.File]::WriteAllText((Join-Path $bundle 'Stepwise.exe'), 'signed')
    Assert-Fails { Assert-ReleaseSignature (Join-Path $bundle 'Stepwise.exe') 'wrong-signer' } 'Wrong signer accepted.'
    $zip = Join-Path $fixture 'portable.zip'
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($bundle,$zip)
    Assert-PortableContents $zip $bundle 'test-thumbprint' (Join-Path $fixture 'extract-valid')
    $script:checks++
    [IO.File]::WriteAllText((Join-Path $bundle 'Stepwise.exe'), 'unsigned')
    $unsignedZip = Join-Path $fixture 'unsigned.zip'
    [IO.Compression.ZipFile]::CreateFromDirectory($bundle,$unsignedZip)
    Assert-Fails { Assert-PortableContents $unsignedZip $bundle 'test-thumbprint' (Join-Path $fixture 'extract-invalid') } 'Unsigned portable executable accepted.'
    $stage = New-Stage 'stage'
    $names = @(Assert-ReleaseArtifacts $stage '9.9.9' 'fixture-commit' 'test-thumbprint')
    Assert-True ($names.Count -eq 3) 'Single installer artifact set incomplete.'
    Assert-Fails { Assert-ReleaseArtifacts $stage '9.9.9' 'wrong-commit' 'test-thumbprint' } 'Wrong commit accepted.'
    Assert-Fails { Assert-ReleaseArtifacts $stage '9.9.8' 'fixture-commit' 'test-thumbprint' } 'Wrong version accepted.'
    Assert-Fails { Assert-ReleaseArtifacts $stage '..\escape' 'fixture-commit' 'test-thumbprint' } 'Version traversal accepted.'
    $legacyStage = New-Stage 'legacy-stage'
    $legacyManifest = Get-Content -LiteralPath (Join-Path $legacyStage 'build-manifest.v9.9.9.json') -Raw | ConvertFrom-Json
    $legacyManifest.artifacts[0].name = 'App06_Stepwise-Setup_v9.9.9.exe'
    [IO.File]::Move((Join-Path $legacyStage 'App06_Stepwise_Setup_v9.9.9.exe'), (Join-Path $legacyStage $legacyManifest.artifacts[0].name))
    Write-ReleaseJson (Join-Path $legacyStage 'build-manifest.json') $legacyManifest
    [IO.File]::WriteAllText((Join-Path $legacyStage 'SHA256SUMS.txt'), "$($legacyManifest.artifacts[0].sha256)  $($legacyManifest.artifacts[0].name)")
    Remove-Item -LiteralPath (Join-Path $legacyStage 'build-manifest.v9.9.9.json'), (Join-Path $legacyStage 'SHA256SUMS.v9.9.9.txt')
    $legacyNames = @(Assert-ReleaseArtifacts $legacyStage '9.9.9' 'fixture-commit' 'test-thumbprint')
    Assert-True (($legacyNames -join ',') -eq 'App06_Stepwise-Setup_v9.9.9.exe,SHA256SUMS.txt,build-manifest.json') 'Legacy single-installer read compatibility failed.'
    Assert-Fails { Assert-ReleaseArtifacts $legacyStage '9.9.9' 'wrong-commit' 'test-thumbprint' } 'Legacy wrong commit accepted.'
    [IO.File]::WriteAllText((Join-Path $legacyStage 'SHA256SUMS.v9.9.9.txt'), 'partial versioned metadata')
    Assert-Fails { Assert-ReleaseArtifacts $legacyStage '9.9.9' 'fixture-commit' 'test-thumbprint' } 'Partial versioned metadata silently fell back to legacy.'
    [IO.File]::AppendAllText((Join-Path $stage $names[0]), 'changed')
    Assert-Fails { Assert-ReleaseArtifacts $stage '9.9.9' 'fixture-commit' 'test-thumbprint' } 'Changed installer accepted.'
    $stage = New-Stage 'stage-clean'
    [IO.File]::AppendAllText((Join-Path $stage 'SHA256SUMS.v9.9.9.txt'), 'changed')
    Assert-Fails { Assert-ReleaseArtifacts $stage '9.9.9' 'fixture-commit' 'test-thumbprint' } 'Changed checksums accepted.'
    $stage = New-Stage 'stage-promotion'
    $release = Join-Path $fixture 'release'
    [IO.Directory]::CreateDirectory($release) | Out-Null
    [IO.File]::WriteAllText((Join-Path $release 'old-version.exe'), 'old official')
    [IO.File]::WriteAllText((Join-Path $release 'build-manifest.json'), 'old manifest')
    $oldInventory = @(Get-BundleInventory $release)
    Assert-Fails { Publish-LocalRelease $stage $release $names { param($name) if ($name -like 'build-manifest.*') { throw 'Injected copy failure' } } } 'Promotion failure ignored.'
    Assert-BundleInventory $release $oldInventory
    $script:checks++
    Publish-LocalRelease $stage $release $names
    Assert-True ([IO.File]::ReadAllText((Join-Path $release 'old-version.exe')) -eq 'old official') 'Old artifact changed.'
    Assert-True ([IO.File]::ReadAllText((Join-Path $release 'build-manifest.json')) -eq 'old manifest') 'Old generic metadata changed.'
    [IO.File]::AppendAllText((Join-Path $stage $names[0]), 'new bytes')
    $protected = @(Get-BundleInventory $release)
    Assert-Fails { Publish-LocalRelease $stage $release $names } 'Different existing version overwritten.'
    Assert-BundleInventory $release $protected
    $script:checks++
    Assert-Fails { Publish-LocalRelease $stage $release @('..\escape.exe') } 'Path traversal allowed.'
    Assert-Fails { Assert-OwnedBuildPath (Join-Path (Split-Path -Parent $fixture) 'outside') $fixture } 'Outside project build path accepted.'
    $mutableStage = New-Stage 'stage-mutating'
    $mutableRelease = Join-Path $fixture 'mutation-release'
    [IO.Directory]::CreateDirectory($mutableRelease) | Out-Null
    [IO.File]::WriteAllText((Join-Path $mutableRelease 'protected.exe'), 'old official')
    $beforeMutation = @(Get-BundleInventory $mutableRelease)
    Assert-Fails {
        Publish-LocalRelease $mutableStage $mutableRelease $names {
            param($name)
            if ($name -like 'build-manifest.*') { [IO.File]::AppendAllText((Join-Path $mutableStage $name), 'changed after preflight') }
        }
    } 'Artifact mutation during promotion accepted.'
    Assert-BundleInventory $mutableRelease $beforeMutation
    $script:checks++
    $script:remoteCommit = 'fixture-commit'
    $script:remoteFiles = @{ 'old-version.exe'='different remote content' }
    $script:uploaded = @()
    $remoteNames = @('old-version.exe','build-manifest.json')
    Assert-Fails { Publish-GitHubRelease $release $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture 'remote-mismatch') } 'Remote mismatch accepted.'
    Assert-True ($script:uploaded.Count -eq 0) 'Uploaded before all remote comparisons completed.'
    $script:remoteFiles['old-version.exe'] = 'old official'
    Publish-GitHubRelease $release $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture 'remote-match')
    Assert-True (($script:uploaded -join ',') -eq 'build-manifest.json') 'Matching existing asset was reuploaded.'
    $script:uploaded = @()
    $script:remoteCommit = 'other-commit'
    Assert-Fails { Publish-GitHubRelease $release $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture 'remote-wrong-tag') } 'Wrong remote tag commit accepted.'
    Assert-True ($script:uploaded.Count -eq 0) 'Uploaded to wrong tag commit.'
    Write-Output "PASS: $script:checks release failure/safety assertions; signatures mocked, no real signing/publication."
} finally {
    $absolute = [IO.Path]::GetFullPath($fixture)
    $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $absolute.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Leaf $absolute) -notlike 'stepwise-release-test-*') { throw 'Unsafe fixture cleanup target.' }
    Remove-Item -LiteralPath $absolute -Recurse -Force
}
