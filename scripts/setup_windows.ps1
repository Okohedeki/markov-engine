param(
    [string]$Python = 'python',
    [string]$EnvironmentPath = '.venv',
    [switch]$Development
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    & $Python -c "import struct, sys; assert sys.platform == 'win32' and struct.calcsize('P') == 8 and sys.version_info[:2] == (3, 11), 'Use 64-bit Python 3.11 for the supported Windows setup'"
    if ($LASTEXITCODE -ne 0) { throw 'Unsupported Python. Pass -Python with the Python 3.11 executable path.' }
    $environmentRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot $EnvironmentPath))
    $servicePython = Join-Path $environmentRoot 'Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $servicePython)) {
        & $Python -m venv $environmentRoot
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
    }
    & $servicePython -c "import pathlib, struct, sys; config=(pathlib.Path(sys.prefix)/'pyvenv.cfg').read_text().lower(); assert sys.prefix != sys.base_prefix and 'include-system-site-packages = false' in config and struct.calcsize('P') == 8 and sys.version_info[:2] == (3, 11), 'Choose a clean Python 3.11 virtual environment with -EnvironmentPath; the existing environment is not changed'"
    if ($LASTEXITCODE -ne 0) { throw 'The existing environment is unsuitable. No packages were installed.' }
    $installTarget = if ($Development) { '.[dev]' } else { '.' }
    & $servicePython -m pip install --constraint packaging/windows-constraints.txt --editable $installTarget
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your connection and retry.' }
    & $servicePython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed.' }
    Write-Output "Ready. Start Markov with: & '$servicePython' -m markov_engine.service --open-browser"
    Write-Output 'The default .venv can also be started with .\run-service.cmd.'
} finally {
    Pop-Location
}
