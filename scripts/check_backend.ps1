$ErrorActionPreference = "Stop"
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -UseBasicParsing -TimeoutSec 5
    Write-Host "Success: Backend is reachable. Status: $($response.StatusCode)"
    Write-Host "Content: $($response.Content)"
}
catch {
    Write-Host "Error: Backend is NOT reachable."
    Write-Host $_.Exception.Message
}
