$ErrorActionPreference = "Stop"

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $toolsDir
$serverDir = Join-Path $projectRoot "home-server"
$pythonExe = Join-Path $serverDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found at $pythonExe"
}

Set-Location $serverDir

$query = "look up latest OpenAI news"

& $pythonExe -c "import asyncio; from app.web_lookup import should_lookup, build_web_context; q='$query'; print('should_lookup=', should_lookup(q)); ctx=asyncio.run(build_web_context(q)); print('context_length=', len(ctx)); print(ctx[:1000])"

Write-Host ""
Write-Host "If context_length is > 0, internet lookup fetch is working." -ForegroundColor Green
$ErrorActionPreference = "Stop"

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $toolsDir
$serverDir = Join-Path $projectRoot "home-server"
$pythonExe = Join-Path $serverDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found at $pythonExe"
}

Set-Location $serverDir

$query = "look up latest OpenAI news"

& $pythonExe -c "import asyncio; from app.web_lookup import should_lookup, build_web_context; q='$query'; print('should_lookup=', should_lookup(q)); ctx=asyncio.run(build_web_context(q)); print('context_length=', len(ctx)); print(ctx[:1000])"

Write-Host ""
Write-Host "If context_length is > 0, internet lookup fetch is working." -ForegroundColor Green
