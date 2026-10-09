# Produce an unsigned application bundle only. Official release files are untouched.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location -LiteralPath $ProjectRoot
. "$PSScriptRoot\release_helpers.ps1"
$Version = ([regex]::Match((Get-Content pyproject.toml -Raw), '(?m)^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')).Groups[1].Value
if (-not $Version) { throw 'A valid project version is required.' }
$Commit = & git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve source commit.' }
$SourceState = @(& git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw 'Cannot check source state.' }
$Dirty = $SourceState.Count -ne 0
$RunRoot = Join-Path $ProjectRoot ('build\unsigned\' + [guid]::NewGuid().ToString('N'))
Assert-OwnedBuildPath $RunRoot $ProjectRoot
[IO.Directory]::CreateDirectory($RunRoot) | Out-Null
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) { $PythonExe = 'python' }
$testCommands = @('python -m pytest tests -q', 'tests/Test-SignToolDiscovery.ps1', 'tests/Test-ReleasePipeline.ps1', 'tests/Test-ReleaseOrchestration.ps1', 'scripts/test_user_data_backup.ps1')
$testLog = Join-Path $RunRoot 'test-results.txt'
$previousQtPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = 'offscreen'
    & $PythonExe -m pytest tests -q 2>&1 | Tee-Object -FilePath $testLog
    if ($LASTEXITCODE -ne 0) { throw 'Application tests failed; build is not release eligible.' }
} finally { $env:QT_QPA_PLATFORM = $previousQtPlatform }
foreach ($test in $testCommands[1..4]) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot $test) 2>&1 | Tee-Object -FilePath $testLog -Append
    if ($LASTEXITCODE -ne 0) { throw "Release test failed: $test" }
}
& $PythonExe -m PyInstaller "$ProjectRoot\installer\stepwise.spec" --noconfirm --distpath "$RunRoot\dist" --workpath "$RunRoot\work"
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed; official release files were not changed.' }
$Bundle = Join-Path $RunRoot 'dist\Stepwise'
if (-not (Test-Path -LiteralPath "$Bundle\Stepwise.exe")) { throw 'Built application is missing.' }
$finalCommit = & git rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $finalCommit -ne $Commit) { throw 'Source commit changed during build.' }
$finalStatus = @(& git status --porcelain)
if ($LASTEXITCODE -ne 0 -or ($finalStatus -join "`n") -cne ($SourceState -join "`n")) { throw 'Source state changed during build.' }
Write-ReleaseJson (Join-Path $RunRoot 'build-input.json') ([ordered]@{
    product_id = 'App06_Stepwise'; version = $Version; git_commit = $Commit
    source_dirty = $Dirty; built_at_utc = [DateTime]::UtcNow.ToString('o')
    tests_passed = $true; test_commands = $testCommands
    test_results_sha256 = (Get-FileHash -LiteralPath $testLog -Algorithm SHA256).Hash.ToLowerInvariant()
    bundle = @(Get-BundleInventory $Bundle)
})
Write-Output "Unsigned bundle: $Bundle"
if ($Dirty) { Write-Warning 'Developer build has uncommitted source changes and cannot be signed as an official release.' }
Write-Output "After committing and rebuilding, run scripts\sign.ps1 -BuildRoot `"$RunRoot`". Signing does not publish unless -Publish is specified."
