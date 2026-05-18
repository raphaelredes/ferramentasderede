$ErrorActionPreference = 'Stop'

# Inputs are placeholder-substituted by RemoteCommands.manage_service. Service
# name and action are validated upstream against strict regex / enum, so by
# the time they land in the literals below they can't break out of the quoted
# string. Action vocabulary: start | stop | restart | pause.

$svc = '__SERVICE_NAME__'
$action = '__ACTION__'

try {
    $existing = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Output "ERROR: serviço '$svc' não encontrado."
        exit 1
    }

    switch ($action) {
        'start'   { Start-Service   -Name $svc -ErrorAction Stop; break }
        'stop'    { Stop-Service    -Name $svc -ErrorAction Stop -Force; break }
        'restart' { Restart-Service -Name $svc -ErrorAction Stop -Force; break }
        'pause'   { Suspend-Service -Name $svc -ErrorAction Stop; break }
        default {
            Write-Output "ERROR: ação inválida '$action'."
            exit 1
        }
    }

    $svcAfter = Get-Service -Name $svc
    Write-Output ("OK: " + $svcAfter.Status)
}
catch {
    Write-Output ("ERROR: " + $_.Exception.Message)
    exit 1
}
