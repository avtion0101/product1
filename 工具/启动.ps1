$ErrorActionPreference = 'Continue'
$projectRoot = Split-Path $PSScriptRoot -Parent
$venvPython = Join-Path $projectRoot '.generator_venv\Scripts\python.exe'

function Test-Python {
    param([string]$Binary, [string[]]$Prefix = @())
    if (-not (Get-Command $Binary -ErrorAction SilentlyContinue)) { return $false }
    try {
        & $Binary @Prefix -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    $candidates = @(
        @{ Binary = 'py'; Prefix = @('-3') },
        @{ Binary = 'python'; Prefix = @() },
        @{ Binary = 'python3'; Prefix = @() },
        @{ Binary = $bundled; Prefix = @() }
    )
    $selected = $null
    foreach ($candidate in $candidates) {
        if (Test-Python -Binary $candidate.Binary -Prefix $candidate.Prefix) {
            $selected = $candidate
            break
        }
    }
    if (-not $selected) {
        throw 'Python 3.11 or newer is required. Install Python and retry.'
    }
    $prefix = $selected.Prefix
    & $selected.Binary @prefix -m venv (Join-Path $projectRoot '.generator_venv')
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the generator virtual environment.' }
}

if (-not (Test-Python -Binary $venvPython)) {
    throw 'The virtual environment uses Python older than 3.11. Move .generator_venv aside and retry with a newer Python.'
}
& $venvPython -c 'import tkinter' 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Python is missing Tk. Install a Python distribution with Tk support.' }
& $venvPython -c 'import docx, pypdf, PIL' 2>$null
if ($LASTEXITCODE -ne 0) {
    & $venvPython -m pip install --disable-pip-version-check --only-binary=:all: -r (Join-Path $PSScriptRoot 'requirements-generator.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and Python version.' }
}

$env:PYTHONPATH = Join-Path $PSScriptRoot '.packages'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $projectRoot
& $venvPython (Join-Path $PSScriptRoot 'studio.py') @args
exit $LASTEXITCODE
