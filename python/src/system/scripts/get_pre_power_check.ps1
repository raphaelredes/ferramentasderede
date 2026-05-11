# Pre-power-action check — fired right before shutdown/restart to surface
# warnings the operator might want before pulling the trigger:
#
#   - uptime_minutes      : how long the host has been up (warn on very recent reboots)
#   - pending_reboot      : True if Windows already has a reboot pending
#   - sessions            : list of {user, state, sessionId, idleSeconds} —
#                           console/disconnected/active. Empty = nobody logged on
#
# All sub-queries are individually wrapped in try/catch so partial failures
# don't blank the whole report. Output is a single JSON line.

try {
    $result = @{
        uptime_minutes  = $null
        last_boot       = "N/A"
        pending_reboot  = $null      # null = could not determine
        pending_reasons = @()        # list of registry keys that indicated pending
        sessions        = @()
    }

    # --- Uptime / Last boot --------------------------------------------------
    try {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        if ($os.LastBootUpTime) {
            $boot = $os.LastBootUpTime
            $result.last_boot = $boot.ToString("yyyy-MM-ddTHH:mm:ss")
            $delta = (Get-Date) - $boot
            $result.uptime_minutes = [int][math]::Round($delta.TotalMinutes)
        }
    } catch {}

    # --- Pending reboot ------------------------------------------------------
    # Multiple registry hints; any one means a reboot is queued. We collect
    # which ones tripped so the UI can show "why" if needed.
    try {
        $hints = @(
            @{ Path = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'; Reason = 'CBS' },
            @{ Path = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'; Reason = 'WindowsUpdate' },
            @{ Path = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\PackagesPending'; Reason = 'CBS-PackagesPending' }
        )
        foreach ($h in $hints) {
            if (Test-Path $h.Path) { $result.pending_reasons += $h.Reason }
        }
        # PendingFileRenameOperations under Session Manager
        try {
            $sm = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name 'PendingFileRenameOperations' -ErrorAction Stop
            if ($sm.PendingFileRenameOperations) { $result.pending_reasons += 'PendingFileRenameOperations' }
        } catch {}
        $result.pending_reboot = ($result.pending_reasons.Count -gt 0)
    } catch {}

    # --- Active sessions -----------------------------------------------------
    # `quser` is the most accurate but text-output. We use it first; if it fails
    # (perms, RD service stopped), fall back to enumerating logon sessions via
    # CIM. We surface only Active / Disconnected sessions — Listen states from
    # RDP services are noise.
    $sessionsFound = $false
    try {
        $rawLines = & quser.exe 2>$null
        if ($LASTEXITCODE -eq 0 -and $rawLines) {
            # Skip header line.
            $headerSkipped = $false
            foreach ($line in $rawLines) {
                if (-not $headerSkipped) { $headerSkipped = $true; continue }
                if (-not $line.Trim()) { continue }
                # Columns are space-aligned; split on 2+ whitespace.
                $cols = $line -split '\s{2,}'
                if ($cols.Count -lt 3) { continue }
                # The leading column can have a leading '>' marking the current
                # user — strip it.
                $userName = $cols[0].TrimStart('>').Trim()
                # Discover where STATE column actually sits — depends on locale.
                $stateCandidate = ($cols | Where-Object { $_ -match '^(Active|Ativo|Disc|Inactiva|Inactivo|Disconnected|Desconectado)$' } | Select-Object -First 1)
                $state = if ($stateCandidate) { $stateCandidate } else { ($cols[-3]) }
                $idleField = $cols[-2]
                $idleSeconds = $null
                if ($idleField -match '^(\d+)\+?:?(\d+)?$') {
                    if ($matches[2]) {
                        $idleSeconds = [int]$matches[1] * 3600 + [int]$matches[2] * 60
                    } else {
                        $idleSeconds = [int]$matches[1] * 60
                    }
                } elseif ($idleField -match '^(\d+)\+(\d+):(\d+)$') {
                    # days+hh:mm
                    $idleSeconds = ([int]$matches[1] * 86400) + ([int]$matches[2] * 3600) + ([int]$matches[3] * 60)
                }
                $result.sessions += @{
                    user         = $userName
                    state        = $state
                    idle_seconds = $idleSeconds
                }
                $sessionsFound = $true
            }
        }
    } catch {}

    # Fallback to CIM if quser produced nothing useful.
    if (-not $sessionsFound) {
        try {
            $explorerProcs = Get-CimInstance Win32_Process -Filter "Name='explorer.exe'" -ErrorAction Stop
            foreach ($p in $explorerProcs) {
                try {
                    $owner = Invoke-CimMethod -InputObject $p -MethodName GetOwner -ErrorAction Stop
                    if ($owner.User) {
                        $u = if ($owner.Domain) { "$($owner.Domain)\$($owner.User)" } else { $owner.User }
                        $result.sessions += @{
                            user         = $u
                            state        = 'Active'   # explorer.exe running = interactive
                            idle_seconds = $null
                        }
                    }
                } catch {}
            }
        } catch {}
    }

    $result | ConvertTo-Json -Depth 4 -Compress
} catch {
    @{
        uptime_minutes  = $null
        last_boot       = "N/A"
        pending_reboot  = $null
        pending_reasons = @()
        sessions        = @()
        error           = $_.Exception.Message
    } | ConvertTo-Json -Depth 4 -Compress
}
