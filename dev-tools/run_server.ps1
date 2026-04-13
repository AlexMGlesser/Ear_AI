param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8765
)

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $toolsDir
$serverDir = Join-Path $projectRoot "home-server"

$env:HOST = $HostAddress
$env:PORT = "$Port"

Set-Location $serverDir
uvicorn app.main:app --host $HostAddress --port $Port --reload
param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8765
)

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $toolsDir
$serverDir = Join-Path $projectRoot "home-server"

$env:HOST = $HostAddress
$env:PORT = "$Port"

Set-Location $serverDir
uvicorn app.main:app --host $HostAddress --port $Port --reload
