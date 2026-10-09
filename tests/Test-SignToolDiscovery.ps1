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
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Find-SuiteSignTool'
}, $true)
if (@($definition).Count -ne 1) { throw 'Expected exactly one signing-tool discovery function.' }
Invoke-Expression $definition[0].Extent.Text

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
function New-ToolStub([string]$Path) {
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    [IO.File]::WriteAllText($Path, 'Not executed: discovery fixture')
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
    Assert-Discovery (Find-SuiteSignTool) $local
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

