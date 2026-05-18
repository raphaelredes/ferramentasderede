$ErrorActionPreference = 'Stop'

# Inputs validated upstream (service name regex, startup type enum). Action
# here is always 'set_startup' but we accept it as a placeholder for symmetry
# with manage_service.ps1. Valid StartupType values: Automatic, Manual,
# Disabled, AutomaticDelayedStart.

$svc = '__SERVICE_NAME__'
$startup = '__STARTUP_TYPE__'

try {
    $existing = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Output "ERROR: serviço '$svc' não encontrado."
        exit 1
    }

    Set-Service -Name $svc -StartupType $startup -ErrorAction Stop
    Write-Output ("OK: StartupType=" + $startup)
}
catch {
    Write-Output ("ERROR: " + $_.Exception.Message)
    exit 1
}
