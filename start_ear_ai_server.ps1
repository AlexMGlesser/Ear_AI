param(
    [string]$ListenHost = "0.0.0.0",
    [int]$Port = 8765,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverDir = Join-Path $root "home-server"
$venvDir = Join-Path $serverDir ".venv"
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
$requirementsFile = Join-Path $serverDir "requirements.txt"
$envFile = Join-Path $serverDir ".env"
$envExample = Join-Path $serverDir ".env.example"
$depsMarker = Join-Path $venvDir ".deps_installed"

if (-not (Test-Path $serverDir)) {
    throw "Could not find home-server folder at $serverDir"
}

Set-Location $serverDir

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
}

if (-not (Test-Path $activateScript)) {
    throw "Virtual environment activation script not found at $activateScript"
}

. $activateScript

if (-not (Test-Path $requirementsFile)) {
    throw "requirements.txt not found at $requirementsFile"
}

if (-not (Test-Path $depsMarker)) {
    Write-Host "Installing Python dependencies..."
    pip install -r requirements.txt
    New-Item -ItemType File -Path $depsMarker -Force | Out-Null
}

if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "Created .env from .env.example. Review $envFile before production use."
}

$reloadArg = if ($NoReload) { "" } else { " --reload" }
$command = "uvicorn app.main:app --host $ListenHost --port $Port$reloadArg"

Write-Host "Starting Ear AI home server..."
Write-Host "Host: $ListenHost"
Write-Host "Port: $Port"
Write-Host "Working directory: $serverDir"
Write-Host ""

Invoke-Expression $command
