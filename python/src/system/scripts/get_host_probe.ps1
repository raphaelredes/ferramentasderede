# Lightweight host probe — single round-trip WMI query batch designed to be
# fired opportunistically (after a Terminal session opens, after TestConnection
# succeeds, etc.) to cache stable signals on the host record:
#
#   MAC address       — never changes for a given NIC; enables future WoL
#   Domain (NetBIOS)  — actual AD domain from Win32_ComputerSystem, not the
#                       one inferred from CIDR settings
#   CurrentUser       — who is logged on right now
#   LastBootUpTime    — to warn against redundant restarts
#   SystemDiskFreeGB  — free space on the C: drive
#
# Designed to fail silently and partially: any individual sub-query going
# wrong just leaves that field as "N/A" so the caller still gets the rest.
try {
    $result = @{
        MACAddress       = "N/A"
        Domain           = "N/A"
        CurrentUser      = "N/A"
        LastBootUpTime   = "N/A"
        SystemDiskFreeGB = $null
    }

    try {
        $cs = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        if ($cs -and $cs.Domain) { $result.Domain = $cs.Domain }
        if ($cs -and $cs.UserName) { $result.CurrentUser = $cs.UserName }
    } catch {}

    try {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        if ($os -and $os.LastBootUpTime) {
            $result.LastBootUpTime = $os.LastBootUpTime.ToString("yyyy-MM-ddTHH:mm:ss")
        }
    } catch {}

    try {
        # Pick the first IPEnabled NIC's MAC. In multi-VLAN hosts we don't
        # have a way to tell here which interface the operator actually
        # reaches the host through; the primary IPEnabled one is the best
        # heuristic without extra hints.
        $nic = Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration -Filter "IPEnabled = true" -ErrorAction Stop |
            Select-Object -First 1
        if ($nic -and $nic.MACAddress) { $result.MACAddress = $nic.MACAddress }
    } catch {}

    try {
        $systemDrive = $env:SystemDrive
        if (-not $systemDrive) { $systemDrive = "C:" }
        $disk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter ("DeviceID = '" + $systemDrive + "'") -ErrorAction Stop
        if ($disk -and $disk.FreeSpace) {
            $result.SystemDiskFreeGB = [math]::Round($disk.FreeSpace / 1GB, 2)
        }
    } catch {}

    # If the operator's session is empty (CIM is sometimes empty when no
    # interactive logon), fall back to enumerating quser/explorer.exe.
    if ($result.CurrentUser -eq "N/A") {
        try {
            $explorer = Get-CimInstance -ClassName Win32_Process -Filter "Name='explorer.exe'" -ErrorAction Stop | Select-Object -First 1
            if ($explorer) {
                $owner = Invoke-CimMethod -InputObject $explorer -MethodName GetOwner -ErrorAction Stop
                if ($owner -and $owner.User) {
                    $u = if ($owner.Domain) { "$($owner.Domain)\$($owner.User)" } else { $owner.User }
                    $result.CurrentUser = $u
                }
            }
        } catch {}
    }

    $result | ConvertTo-Json -Compress
} catch {
    @{
        MACAddress       = "N/A"
        Domain           = "N/A"
        CurrentUser      = "N/A"
        LastBootUpTime   = "N/A"
        SystemDiskFreeGB = $null
        error            = $_.Exception.Message
    } | ConvertTo-Json -Compress
}
