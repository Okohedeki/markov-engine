[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,

    [switch]$NoReload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envFile = Join-Path $repoRoot ".env"
$dataDirectory = Join-Path $repoRoot "data"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $dataDirectory)) {
    New-Item -ItemType Directory -Path $dataDirectory | Out-Null
}

$usingOfflineDefaults = -not (Test-Path -LiteralPath $envFile)
if ($usingOfflineDefaults) {
    $env:LLM_BACKEND = "heuristic"
    $env:EMBED_BACKEND = "hash"
    $env:SEARCH_ENABLED = "false"
    $env:TRANSCRIBE_MEDIA = "false"
    $env:MARKOV_DATABASE_PATH = "data/local-markov.db"
    $env:MARKOV_API_KEYS = '{"local-customer-key":"local-customer"}'
    $env:MARKOV_INTERNAL_API_KEYS = '{"local-review-key":"reviewer-1"}'
    $env:MARKOV_WEB_SESSION_SECRET = "local-development-only-change-before-deploy"
    $env:MARKOV_OPENING_CREDITS = "100"
    $env:MARKOV_API_RATE_LIMIT_PER_MINUTE = "600"
}

$pythonExecutable = $null
$pythonPrefix = @()
if (Test-Path -LiteralPath $venvPython) {
    $pythonExecutable = $venvPython
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExecutable = (Get-Command py).Source
    $pythonPrefix = @("-3.11")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExecutable = (Get-Command python).Source
} else {
    throw "Python 3.11+ was not found. Install Python, then run this launcher again."
}

$serverArguments = @(
    "-m", "uvicorn", "markov_engine.api:app",
    "--host", "127.0.0.1",
    "--port", $Port.ToString()
)
if (-not $NoReload) {
    $serverArguments += @("--reload", "--reload-dir", "markov_engine")
}

Push-Location $repoRoot
try {
    & $pythonExecutable @pythonPrefix -c "import fastapi, jinja2, uvicorn, markov_engine"
    if ($LASTEXITCODE -ne 0) {
        throw "Markov dependencies are missing. Run: py -3.11 -m pip install -e ."
    }

    Write-Host ""
    Write-Host "Markov localhost is starting" -ForegroundColor Cyan
    Write-Host "  Landing page: http://127.0.0.1:$Port/"
    Write-Host "  SaaS workspace: http://127.0.0.1:$Port/app/login"
    Write-Host "  API docs: http://127.0.0.1:$Port/docs"
    Write-Host "  API base: http://127.0.0.1:$Port/v2"
    if ($usingOfflineDefaults) {
        Write-Host "  Customer key: local-customer-key"
        Write-Host "  Reviewer key: local-review-key"
        Write-Host "  Mode: offline heuristic + hash embeddings; web search disabled"
        Write-Host "  Database: data/local-markov.db"
    } else {
        Write-Host "  Configuration: .env"
    }
    Write-Host ""
    Write-Host "Press Ctrl+C to stop Markov." -ForegroundColor DarkGray
    Write-Host ""

    & $pythonExecutable @pythonPrefix @serverArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Markov exited with code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
