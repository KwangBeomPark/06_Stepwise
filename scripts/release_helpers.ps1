# Pure release helpers: importing this file never signs, builds, or publishes.
Set-StrictMode -Version Latest

function Write-ReleaseJson($Path, $Value) {
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 12), (New-Object Text.UTF8Encoding($false)))
}

function Assert-OwnedBuildPath([string]$Path, [string]$ProjectRoot) {
    $root = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
    $target = [IO.Path]::GetFullPath($Path)
    if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Build output must stay inside the project.' }
    $ancestor = $target
    while ($ancestor.Length -gt $root.Length) {
        if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Build output ancestors must not contain reparse points.' }
        $ancestor = Split-Path -Parent $ancestor
    }
}

function Get-BundleInventory([string]$Directory) {
    $root = (Resolve-Path -LiteralPath $Directory).Path.TrimEnd('\')
    if ((Get-Item -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Release input directory must not be a reparse point.'
    }
    $items = @(Get-ChildItem -LiteralPath $root -Recurse -Force)
    if (@($items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
        throw 'Release inputs must not contain reparse points.'
    }
    @($items | Where-Object { -not $_.PSIsContainer } | Sort-Object FullName | ForEach-Object {
        [ordered]@{ name = $_.FullName.Substring($root.Length + 1).Replace('\', '/'); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
}

function Assert-BundleInventory([string]$Directory, $Inventory) {
    $actual = @(Get-BundleInventory $Directory)
    if ($actual.Count -ne @($Inventory).Count) { throw 'Bundle file count does not match provenance.' }
    foreach ($entry in $Inventory) {
        $match = @($actual | Where-Object { $_.name -ceq $entry.name -and $_.sha256 -ceq $entry.sha256 })
        if ($match.Count -ne 1) { throw "Bundle provenance mismatch: $($entry.name)" }
    }
}

function Assert-ReleaseSignature([string]$Path, [string]$Thumbprint) {
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or
        $signature.SignerCertificate.Thumbprint -ne $Thumbprint -or -not $signature.TimeStamperCertificate) {
        throw "Valid expected-signer timestamped signature required: $(Split-Path -Leaf $Path)"
    }
}

function Assert-PortableContents([string]$ZipPath, [string]$BundlePath, [string]$Thumbprint, [string]$ExtractionPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        foreach ($entry in $archive.Entries) {
            if ($entry.FullName -match '(^[/\\]|(^|[/\\])\.\.([/\\]|$)|:)' -or
                $entry.FullName -match '(^|[/\\])UserSetting([/\\]|$)' -or
                $entry.FullName -match '^(macros|results)([/\\]|$)') { throw 'Unsafe portable ZIP entry.' }
        }
    } finally { $archive.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $ExtractionPath)
    Assert-BundleInventory $ExtractionPath @(Get-BundleInventory $BundlePath)
    Assert-ReleaseSignature (Join-Path $ExtractionPath 'Stepwise.exe') $Thumbprint
}

function Assert-ReleaseArtifacts([string]$Stage, [string]$Version, [string]$Commit, [string]$Thumbprint) {
    if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid release version.' }
    $manifestName = "build-manifest.v$Version.json"
    $checksumName = "SHA256SUMS.v$Version.txt"
    $legacy = $false
    # Read the previous single-installer contract without creating or replacing its metadata.
    if (-not (Test-Path -LiteralPath (Join-Path $Stage $manifestName))) {
        if (Test-Path -LiteralPath (Join-Path $Stage $checksumName)) { throw 'Incomplete versioned release metadata.' }
        $manifestName = 'build-manifest.json'
        $checksumName = 'SHA256SUMS.txt'
        $legacy = $true
    }
    $manifest = Get-Content -LiteralPath (Join-Path $Stage $manifestName) -Raw | ConvertFrom-Json
    if ($manifest.product_id -ne 'App06_Stepwise' -or $manifest.version -ne $Version -or
        $manifest.git_commit -ne $Commit -or $manifest.certificate_thumbprint -ne $Thumbprint) { throw 'Release identity mismatch.' }
    $expected = @($(if ($legacy) { "App06_Stepwise-Setup_v$Version.exe" } else { "App06_Stepwise_Setup_v$Version.exe" }))
    if (@($manifest.artifacts).Count -ne 1) { throw 'Release artifact count mismatch.' }
    $entry = @($manifest.artifacts | Where-Object { $_.name -ceq $expected[0] })
    if ($entry.Count -ne 1) { throw 'Release artifact name mismatch.' }
    $path = Join-Path $Stage $expected[0]
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -cne $entry[0].sha256) { throw "Release artifact checksum mismatch: $($expected[0])" }
    Assert-ReleaseSignature $path $Thumbprint
    $checksums = (Get-Content -LiteralPath (Join-Path $Stage $checksumName)).Trim()
    $expectedLine = "$hash  $($expected[0])"
    if ($checksums -cne $expectedLine) { throw 'Checksum list mismatch.' }
    return $expected + @($checksumName, $manifestName)
}

function Publish-LocalRelease([string]$Stage, [string]$ReleaseRoot, [string[]]$Names, [scriptblock]$BeforeCopy = {}) {
    # Existing versioned artifacts and metadata are never overwritten, even with identical bytes.
    [IO.Directory]::CreateDirectory($ReleaseRoot) | Out-Null
    if ((Get-Item -LiteralPath $ReleaseRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Release directory must not be a reparse point.' }
    $hashes = @{}
    foreach ($name in $Names) {
        if ([IO.Path]::GetFileName($name) -cne $name) { throw 'Promotion accepts leaf names only.' }
        $hashes[$name] = (Get-FileHash -LiteralPath (Join-Path $Stage $name)).Hash
        $target = Join-Path $ReleaseRoot $name
        if (Test-Path -LiteralPath $target) {
            if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Release artifact must not be a reparse point.' }
            if ((Get-FileHash -LiteralPath $target).Hash -ne $hashes[$name]) { throw "Existing version artifact differs; use a new version: $name" }
        }
    }
    $created = @()
    try {
        foreach ($name in $Names) {
            $target = Join-Path $ReleaseRoot $name
            if (Test-Path -LiteralPath $target) { continue }
            & $BeforeCopy $name
            $temporary = Join-Path $ReleaseRoot ('.pending-' + [guid]::NewGuid().ToString('N'))
            try {
                Copy-Item -LiteralPath (Join-Path $Stage $name) -Destination $temporary
                if ((Get-FileHash -LiteralPath $temporary).Hash -ne $hashes[$name]) { throw 'Staged artifact changed during promotion.' }
                [IO.File]::Move($temporary, $target)
                $created += $name
            } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
        }
    } catch {
        foreach ($name in $created) {
            $target = Join-Path $ReleaseRoot $name
            if ((Get-FileHash -LiteralPath $target).Hash -ne $hashes[$name]) { throw 'Rollback refused: promoted file changed externally. Existing official files were untouched.' }
            Remove-Item -LiteralPath $target -Force
        }
        throw
    }
}
function Publish-GitHubRelease([string]$ReleaseRoot, [string[]]$Names, [string]$Tag, [string]$Commit, [string]$DownloadRoot) {
    # Never create/move tags, delete releases/assets, or overwrite an existing asset.
    $tagRef = & gh api "repos/{owner}/{repo}/git/ref/tags/$Tag"
    if ($LASTEXITCODE -ne 0) { throw 'An existing remote release tag is required.' }
    $reference = $tagRef | ConvertFrom-Json
    $object = $reference.object
    while ($object.type -eq 'tag') {
        $tagObject = & gh api "repos/{owner}/{repo}/git/tags/$($object.sha)"
        if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve annotated remote release tag.' }
        $object = ($tagObject | ConvertFrom-Json).object
    }
    if ($object.type -ne 'commit' -or $object.sha -ne $Commit) { throw 'Remote tag does not point to the verified source commit.' }
    $allReleases = & gh api 'repos/{owner}/{repo}/releases?per_page=100' --paginate --slurp
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect remote releases; no publication attempted.' }
    $pages = $allReleases | ConvertFrom-Json
    $existing = @($pages | ForEach-Object { $_ } | Where-Object { $_.tag_name -eq $Tag })
    if ($existing.Count -gt 1) { throw 'Ambiguous remote release.' }
    $missing = @()
    foreach ($name in $Names) {
        if ([IO.Path]::GetFileName($name) -cne $name) { throw 'Publication accepts leaf names only.' }
        $remoteAsset = @()
        if ($existing.Count) { $remoteAsset = @($existing[0].assets | Where-Object { $_.name -ceq $name }) }
        if ($remoteAsset.Count -gt 1) { throw 'Duplicate remote asset name.' }
        if ($remoteAsset.Count) {
            $download = Join-Path $DownloadRoot ('before-' + [guid]::NewGuid().ToString('N'))
            [IO.Directory]::CreateDirectory($download) | Out-Null
            & gh release download $Tag --pattern $name --dir $download
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $download $name))) { throw 'Cannot verify existing remote asset.' }
            if ((Get-FileHash -LiteralPath (Join-Path $download $name)).Hash -ne
                (Get-FileHash -LiteralPath (Join-Path $ReleaseRoot $name)).Hash) { throw "Existing remote asset differs; use a new version: $name" }
        } else { $missing += Join-Path $ReleaseRoot $name }
    }
    if (-not $existing.Count) {
        & gh release create $Tag @missing --verify-tag --title "Stepwise $Tag" --generate-notes
        if ($LASTEXITCODE -ne 0) { throw 'Release creation failed. Retry only with this verified set.' }
    } elseif ($missing.Count) {
        & gh release upload $Tag @missing
        if ($LASTEXITCODE -ne 0) { throw 'Missing-asset upload failed. Existing assets were not overwritten.' }
    }
    foreach ($name in $Names) {
        $download = Join-Path $DownloadRoot ('after-' + [guid]::NewGuid().ToString('N'))
        [IO.Directory]::CreateDirectory($download) | Out-Null
        & gh release download $Tag --pattern $name --dir $download
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $download $name)) -or
            (Get-FileHash -LiteralPath (Join-Path $download $name)).Hash -ne (Get-FileHash -LiteralPath (Join-Path $ReleaseRoot $name)).Hash) {
            throw "Published asset verification failed: $name. Existing remote files were retained."
        }
    }
    Write-Output 'Remote asset bytes verified against the prepared local set.'
}
