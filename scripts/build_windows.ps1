param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    & $Python -c "import struct, sys; assert sys.platform == 'win32' and struct.calcsize('P') == 8 and sys.version_info[:2] == (3, 11), 'Build with 64-bit Python 3.11 on Windows'"
    if ($LASTEXITCODE -ne 0) { throw 'Unsupported build interpreter.' }
    $buildPython = Join-Path $repoRoot 'build/windows-env/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $buildPython)) {
        & $Python -m venv build/windows-env
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated build environment.' }
    }
    & $buildPython -m pip install --constraint packaging/windows-constraints.txt . pyinstaller pillow
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the Windows build dependencies.' }
    & $buildPython packaging/make_windows_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate the Markov icon.' }
    & $buildPython -m PyInstaller --noconfirm --distpath dist/windows --workpath build/windows packaging/Markov.spec
    if ($LASTEXITCODE -ne 0) { throw 'The Windows executable build failed.' }
    $executable = Join-Path $repoRoot 'dist/windows/Markov.exe'
    & $executable --check --no-browser --data-dir (Join-Path $repoRoot 'build/windows-check')
    if ($LASTEXITCODE -ne 0) { throw 'The packaged configuration check failed.' }
    $digest = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$executable.sha256" -Value "$digest  Markov.exe" -Encoding ascii
    Write-Output "Built $executable"
} finally {
    Pop-Location
}
