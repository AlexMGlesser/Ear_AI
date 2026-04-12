param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8765
)

$env:HOST = $HostAddress
$env:PORT = "$Port"

uvicorn app.main:app --host $HostAddress --port $Port --reload
