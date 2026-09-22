$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$pythonBin = Join-Path $runtimeRoot 'python\python.exe'
if (-not (Test-Path -LiteralPath $pythonBin)) { throw 'Codex bundled Python not found. Load workspace dependencies first.' }
$env:PYTHONPATH = Join-Path $PSScriptRoot '.packages'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:GENERATOR_RUNTIME = $runtimeRoot
& $pythonBin -c 'import tkinter, docx, pypdf, PIL'
if ($LASTEXITCODE -ne 0) { throw 'Required bundled dependencies are missing.' }
Set-Location -LiteralPath $projectRoot
& $pythonBin (Join-Path $PSScriptRoot 'studio.py') @args
exit $LASTEXITCODE
