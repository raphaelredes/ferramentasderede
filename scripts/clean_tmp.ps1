# Script to clean the 'tmp' directory
$tmpDir = Join-Path $PSScriptRoot "..\tmp"

if (Test-Path $tmpDir) {
    Get-ChildItem -Path $tmpDir -Recurse | Remove-Item -Force -Recurse
    Write-Host "Cleaned tmp directory: $tmpDir"
} else {
    Write-Host "tmp directory not found: $tmpDir"
}
