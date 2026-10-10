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
function Reset-RemoteFixture {
    $script:remoteDraft = $true
    $script:remoteExists = $true
    $script:remotePre = $false
    $script:remoteState = 'uploaded'
    $script:remoteCommit = 'fixture-commit'
    $script:remoteOrigin = 'https://github.com/KwangBeomPark/06_Stepwise.git'
    $script:remoteFiles = @{}
    $script:uploaded = @()
    $script:edits = 0
    $script:creates = 0
    $script:failUpload = $false
    $script:corruptUpload = $false
    $script:omitDraft = $false
    $script:omitState = $false
    $script:omitPublished = $false
}
function git {
    if (($args -join ' ') -ne 'remote get-url origin') { throw 'Unexpected Git operation in fixture.' }
    $global:LASTEXITCODE = 0
    return $script:remoteOrigin
}
Reset-RemoteFixture
function gh {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'api') {
        if ($args[1] -notlike 'repos/KwangBeomPark/06_Stepwise/*') { throw 'API repository was not pinned.' }
    } else {
        $repoIdx = [Array]::IndexOf($args, '--repo')
        if ($repoIdx -lt 0 -or $args[$repoIdx + 1] -cne 'KwangBeomPark/06_Stepwise') { throw 'Release repository was not pinned.' }
    }
    if ($args[0] -eq 'api') {
        if ($args[1] -like '*/git/ref/tags/*') {
            return (@{ object=@{ type='commit'; sha=$script:remoteCommit } } | ConvertTo-Json -Compress)
        }
        if (-not $script:remoteExists -or ($script:omitPublished -and -not $script:remoteDraft)) { return '[[]]' }
        $assets = @($script:remoteFiles.Keys | ForEach-Object {
            $asset = [ordered]@{ name=$_ }
            if (-not $script:omitState) { $asset.state=$script:remoteState }
            [pscustomobject]$asset
        })
        $release = [ordered]@{ tag_name='v9.9.9'; prerelease=$script:remotePre; assets=$assets }
        if (-not $script:omitDraft) { $release.draft=$script:remoteDraft }
        return ('[[' + ($release | ConvertTo-Json -Depth 5 -Compress) + ']]')
    }
    if ($args[0] -eq 'release' -and $args[1] -eq 'download') {
        $patternIdx = [Array]::IndexOf($args, '--pattern')
        $name = if ($patternIdx -ge 0) { $args[$patternIdx + 1] } else { $args[4] }
        $dirIdx = [Array]::IndexOf($args, '--dir')
        $directory = if ($dirIdx -ge 0) { $args[$dirIdx + 1] } else { $args[6] }
        [IO.File]::WriteAllText((Join-Path $directory $name), $script:remoteFiles[$name])
        return
    }
    if ($args[0] -eq 'release' -and ($args[1] -eq 'create' -or $args[1] -eq 'upload')) {
        if ($args[1] -eq 'create') {
            if ($args -notcontains '--draft') { throw 'New release was not created as a draft.' }
            $script:remoteDraft = $true
            $script:remoteExists = $true
            $script:creates++
        }
        if ($script:failUpload) { $global:LASTEXITCODE=1; return }
        for ($i = 3; $i -lt $args.Count; $i++) {
            if ($args[$i].StartsWith('--')) { break }
            $path = $args[$i]
            $name = Split-Path -Leaf $path
            $script:uploaded += $name
            $script:remoteFiles[$name] = [IO.File]::ReadAllText($path)
            if ($script:corruptUpload) { $script:remoteFiles[$name] += 'corrupted upload' }
        }
        return
    }
    if ($args[0] -eq 'release' -and $args[1] -eq 'edit') {
        if ($args -contains '--draft=false') {
            $script:edits++
            $script:remoteDraft = $false
        }
        return
    }
    throw "Unexpected GitHub operation in fixture: $($args -join ' ')"
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
    $remoteRoot = New-Stage 'remote-source'
    $remoteNames = @(Assert-ReleaseArtifacts $remoteRoot '9.9.9' 'fixture-commit' 'test-thumbprint')
    Reset-RemoteFixture
    $script:remoteFiles[$remoteNames[0]] = 'different remote content'
    Assert-Fails { Publish-GitHubRelease $remoteRoot $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture 'remote-mismatch') } 'Remote mismatch accepted.'
    Assert-True ($script:uploaded.Count -eq 0 -and $script:edits -eq 0) 'Mutated release before remote comparisons completed.'
    $script:remoteFiles[$remoteNames[0]] = [IO.File]::ReadAllText((Join-Path $remoteRoot $remoteNames[0]))
    Publish-GitHubRelease $remoteRoot $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture 'remote-match')
    Assert-True (($script:uploaded -join ',') -eq ($remoteNames[1..2] -join ',')) 'Matching existing installer was reuploaded.'
    Assert-True ($script:edits -eq 1 -and -not $script:remoteDraft -and $script:remoteFiles.Count -eq 3) 'Verified draft was not published with exactly three assets.'
    foreach ($badCase in @('extra','pending','missing-state','missing-draft','string-draft','public','prerelease','origin','tag-commit')) {
        Reset-RemoteFixture
        $script:remoteFiles[$remoteNames[0]] = [IO.File]::ReadAllText((Join-Path $remoteRoot $remoteNames[0]))
        switch ($badCase) {
            'extra' { $script:remoteFiles['unexpected.zip']='extra' }
            'pending' { $script:remoteState='pending' }
            'missing-state' { $script:omitState=$true }
            'missing-draft' { $script:omitDraft=$true }
            'string-draft' { $script:remoteDraft='false' }
            'public' { $script:remoteDraft=$false }
            'prerelease' { $script:remotePre=$true }
            'origin' { $script:remoteOrigin='https://github.com/KwangBeomPark/other.git' }
            'tag-commit' { $script:remoteCommit='other-commit' }
        }
        Assert-Fails { Publish-GitHubRelease $remoteRoot $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture "remote-$badCase") } "Bad remote state accepted: $badCase"
        Assert-True ($script:uploaded.Count -eq 0 -and $script:edits -eq 0 -and $script:creates -eq 0) "Remote mutation before rejection: $badCase"
    }
    foreach ($badCase in @('two-files','duplicate','wrong-version','wrong-name')) {
        Reset-RemoteFixture
        $badNames = @($remoteNames)
        $tag = 'v9.9.9'
        switch ($badCase) {
            'two-files' { $badNames=@($remoteNames[0..1]) }
            'duplicate' { $badNames=@($remoteNames[0],$remoteNames[1],$remoteNames[1]) }
            'wrong-version' { $tag='v9.9.8' }
            'wrong-name' { $badNames[0]='old-version.exe' }
        }
        Assert-Fails { Publish-GitHubRelease $remoteRoot $badNames $tag 'fixture-commit' (Join-Path $fixture "remote-$badCase") } "Bad local contract accepted: $badCase"
        Assert-True ($script:uploaded.Count -eq 0 -and $script:edits -eq 0 -and $script:creates -eq 0) "Remote mutation for bad local contract: $badCase"
    }
    Reset-RemoteFixture
    $script:remoteExists=$false
    Publish-GitHubRelease $remoteRoot $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture 'remote-fresh')
    Assert-True ($script:creates -eq 1 -and $script:edits -eq 1 -and -not $script:remoteDraft -and $script:uploaded.Count -eq 3) 'Fresh release did not follow verified draft-first publication.'
    foreach ($badCase in @('create-failure','upload-failure','corrupt-upload','pending-after-upload')) {
        Reset-RemoteFixture
        if ($badCase -ne 'upload-failure') { $script:remoteExists=$false }
        if ($badCase -like '*failure') { $script:failUpload=$true }
        if ($badCase -eq 'corrupt-upload') { $script:corruptUpload=$true }
        if ($badCase -eq 'pending-after-upload') { $script:remoteState='pending' }
        Assert-Fails { Publish-GitHubRelease $remoteRoot $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture "remote-$badCase") } "Bad upload accepted: $badCase"
        Assert-True ($script:remoteDraft -and $script:edits -eq 0) "Failed upload or verification publicly exposed a draft: $badCase"
    }
    Reset-RemoteFixture
    $script:omitPublished=$true
    Assert-Fails { Publish-GitHubRelease $remoteRoot $remoteNames 'v9.9.9' 'fixture-commit' (Join-Path $fixture 'remote-missing-published') } 'Missing published release was accepted.'
    Assert-True ($script:edits -eq 1) 'Missing postpublication fixture did not reach state verification.'
    Assert-Fails { Assert-GitHubReleaseIdentity ([pscustomobject]@{tag_name='v9.9.8'; draft=$true; prerelease=$false; assets=@()}) 'v9.9.9' $true } 'Wrong remote tag identity accepted.'
    Write-Output "PASS: $script:checks release failure/safety assertions; signatures mocked, no real signing/publication."
} finally {
    $absolute = [IO.Path]::GetFullPath($fixture)
    $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $absolute.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Leaf $absolute) -notlike 'stepwise-release-test-*') { throw 'Unsafe fixture cleanup target.' }
    Remove-Item -LiteralPath $absolute -Recurse -Force
}
