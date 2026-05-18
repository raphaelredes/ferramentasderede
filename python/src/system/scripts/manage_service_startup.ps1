$ErrorActionPreference = 'Stop'

# Inputs validated upstream (service name regex, startup type enum). Valid
# StartupType values: Automatic, Manual, Disabled, AutomaticDelayedStart.
#
# Note: PowerShell 5.1's `Set-Service -StartupType` does NOT accept
# AutomaticDelayedStart — that enumerator only exists in PS 6+. Since most
# managed Windows targets still ship with PS 5.1, we shell out to sc.exe for
# that case. The other three values go through Set-Service as before.

$svc = '__SERVICE_NAME__'
$startup = '__STARTUP_TYPE__'

try {
    $existing = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Output "ERROR: serviço '$svc' não encontrado."
        exit 1
    }

    if ($startup -eq 'AutomaticDelayedStart') {
        # sc.exe rewrites the registry entry directly — works on every
        # supported Windows since at least Windows 7.
        & sc.exe config "$svc" start= delayed-auto | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Output "ERROR: sc.exe config retornou código $LASTEXITCODE."
            exit 1
        }
    }
    else {
        Set-Service -Name $svc -StartupType $startup -ErrorAction Stop
    }
    Write-Output ("OK: StartupType=" + $startup)
}
catch {
    Write-Output ("ERROR: " + $_.Exception.Message)
    exit 1
}
