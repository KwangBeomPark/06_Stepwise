# Exercise only discovery extracted from the signing script; never run signing/service operations.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $repositoryRoot 'scripts\sign.ps1'), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw "Signing script has syntax errors: $parseErrors" }
$definition = $ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in @('Get-SuiteToolArchitecture','Find-SuiteSignTool')
}, $true)
if (@($definition).Count -ne 2) { throw 'Expected architecture and discovery functions.' }
foreach ($function in $definition) { Invoke-Expression $function.Extent.Text }

$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('suite-discovery-' + [guid]::NewGuid().ToString('N'))
$projectRoot = Join-Path $testRoot 'app'
$oldProgramFiles = $env:ProgramFiles
$oldProgramFilesX86 = ${env:ProgramFiles(x86)}
$script:stubCommand = $null
function Get-Command {
    param([string]$Name, [object]$ErrorAction)
    return $script:stubCommand
}
$assertions = 0
function Assert-Discovery([string]$Actual, [string]$Expected) {
    if ($Actual -ne $Expected) { throw "Discovery mismatch: $Actual / $Expected" }
    $script:assertions++
}
function New-ToolStub([string]$Path, [uint16]$Machine = 0x8664) {
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $bytes = New-Object byte[] 128
    [Array]::Copy([BitConverter]::GetBytes([uint16]0x5a4d), 0, $bytes, 0, 2)
    [Array]::Copy([BitConverter]::GetBytes([int]64), 0, $bytes, 60, 4)
    [Array]::Copy([BitConverter]::GetBytes([uint32]0x4550), 0, $bytes, 64, 4)
    [Array]::Copy([BitConverter]::GetBytes($Machine), 0, $bytes, 68, 2)
    [IO.File]::WriteAllBytes($Path, $bytes)
    return (Resolve-Path -LiteralPath $Path).Path
}
try {
    [IO.Directory]::CreateDirectory($projectRoot) | Out-Null
    $env:ProgramFiles = Join-Path $testRoot 'sdk'
    ${env:ProgramFiles(x86)} = ''
    $explicit = New-ToolStub (Join-Path $testRoot 'tool folder ż\signtool.exe')
    Assert-Discovery (Find-SuiteSignTool -RequestedPath $explicit) $explicit
    $failed = $false
    try { Find-SuiteSignTool -RequestedPath (Join-Path $testRoot 'missing.exe') | Out-Null }
    catch { $failed = $true }
    if (-not $failed) { throw 'A missing explicitly requested tool must fail.' }
    $assertions++

    $script:stubCommand = [pscustomobject]@{ Source = $explicit }
    Assert-Discovery (Find-SuiteSignTool) $explicit
    $script:stubCommand = $null

    $older = New-ToolStub (Join-Path $env:ProgramFiles 'Windows Kits\10\bin\10.0.9.0\x64\signtool.exe')
    $newer = New-ToolStub (Join-Path $env:ProgramFiles 'Windows Kits\10\bin\10.0.10.0\x64\signtool.exe')
    Assert-Discovery (Find-SuiteSignTool) $newer

    $local = New-ToolStub (Join-Path $projectRoot 'tools\signtool\signtool.exe')
    $script:stubCommand = [pscustomobject]@{ Source = $explicit }
    Assert-Discovery (Find-SuiteSignTool) $newer
    $x86 = New-ToolStub (Join-Path $env:ProgramFiles 'Windows Kits\10\bin\10.0.10.0\x86\signtool.exe') 0x014c
    Assert-Discovery (Find-SuiteSignTool -Architecture x86) $x86
    Assert-Discovery (Get-SuiteToolArchitecture $x86) 'x86'
    $arm = New-ToolStub (Join-Path $testRoot 'arm64\signtool.exe') 0xaa64
    Assert-Discovery (Get-SuiteToolArchitecture $arm) 'arm64'
    Remove-Item -LiteralPath $newer,$older
    Assert-Discovery (Find-SuiteSignTool) $local
    New-ToolStub $local 0x014c | Out-Null
    Assert-Discovery (Find-SuiteSignTool) $explicit
    $script:stubCommand = [pscustomobject]@{ Source = $local }
    $failed = $false
    try { Find-SuiteSignTool | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw 'Automatic x64 discovery accepted an x86 tool.' }
    $assertions++
    Assert-Discovery (Find-SuiteSignTool -RequestedPath $local) $local
    [IO.File]::WriteAllText($local, 'Invalid PE')
    $failed = $false
    try { Get-SuiteToolArchitecture $local | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw 'Invalid executable accepted.' }
    $assertions++
    Write-Output ("PASS: {0} discovery assertions; no signing or service changes." -f $assertions)
}
finally {
    $env:ProgramFiles = $oldProgramFiles
    ${env:ProgramFiles(x86)} = $oldProgramFilesX86
    $resolved = [IO.Path]::GetFullPath($testRoot)
    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $resolved) -notlike 'suite-discovery-*') {
        throw 'Refusing cleanup outside the owned discovery fixture.'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
