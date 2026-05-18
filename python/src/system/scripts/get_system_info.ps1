
try {
    # 1. OS Info
    $os = Get-WmiObject Win32_OperatingSystem -ErrorAction Stop
    if (-not $os) { throw "Não foi possível obter informações do sistema operacional." }

    $osInfo = @{
        OS             = $os.Caption
        OS_Version     = $os.Version
        LastBootUpTime = "N/A"
        InstallDate    = "N/A"
    }
    
    if ($os.LastBootUpTime) {
        try { $osInfo.LastBootUpTime = [Management.ManagementDateTimeConverter]::ToDateTime($os.LastBootUpTime).ToString("yyyy-MM-ddTHH:mm:ss") } catch {}
    }
    if ($os.InstallDate) {
        try { $osInfo.InstallDate = [Management.ManagementDateTimeConverter]::ToDateTime($os.InstallDate).ToString("yyyy-MM-ddTHH:mm:ss") } catch {}
    }
            
    # 2. CPU Info
    $cpu = Get-WmiObject Win32_Processor | Select-Object -First 1
    $cpuInfo = if ($cpu) { $cpu.Name } else { "N/A" }
            
    # 3. RAM + Domain (Win32_ComputerSystem é único query — aproveita.)
    $ram = Get-WmiObject Win32_ComputerSystem
    $ramGB = if ($ram) { [math]::Round($ram.TotalPhysicalMemory / 1GB, 2) } else { 0 }
    $domain = if ($ram -and $ram.Domain) { $ram.Domain } else { "N/A" }
            
    # 4. Disk Info
    $disks = Get-WmiObject Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 } | ForEach-Object {
        @{
            DeviceID   = $_.DeviceID
            VolumeName = $_.VolumeName
            Total_GB   = [math]::Round($_.Size / 1GB, 2)
            Free_GB    = [math]::Round($_.FreeSpace / 1GB, 2)
        }
    }
            
    # 5. Network Info (Extended)
    $networkInfo = @{
        SubnetMask = "N/A"
        Gateway    = "N/A"
        DNSServers = "N/A"
        DHCPServer = "N/A"
        Interface  = "N/A"
        LinkSpeed  = "N/A"
        MACAddress = "N/A"
    }

    try {
        $netConfig = Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object { $_.IPAddress -contains '__TARGET_IP__' } | Select-Object -First 1
    
        if ($netConfig) {
            $networkInfo.SubnetMask = if ($netConfig.IPSubnet) { $netConfig.IPSubnet[0] } else { "N/A" }
            $networkInfo.Gateway = if ($netConfig.DefaultIPGateway) { $netConfig.DefaultIPGateway -join ", " } else { "N/A" }
            $networkInfo.DNSServers = if ($netConfig.DNSServerSearchOrder) { $netConfig.DNSServerSearchOrder -join ", " } else { "N/A" }
            $networkInfo.DHCPServer = if ($netConfig.DHCPServer) { $netConfig.DHCPServer } else { "N/A" }
            $networkInfo.MACAddress = $netConfig.MACAddress
        
            # Get Interface Name and Speed using Index
            $adapter = Get-WmiObject Win32_NetworkAdapter | Where-Object { $_.Index -eq $netConfig.Index } | Select-Object -First 1
            if ($adapter) {
                $networkInfo.Interface = $adapter.NetConnectionID
                if ($adapter.Speed) {
                    $speed = $adapter.Speed
                    if ($speed -ge 1GB) {
                        $networkInfo.LinkSpeed = "$([math]::Round($speed / 1GB, 1)) Gbps"
                    }
                    elseif ($speed -ge 1MB) {
                        $networkInfo.LinkSpeed = "$([math]::Round($speed / 1MB, 0)) Mbps"
                    }
                    else {
                        $networkInfo.LinkSpeed = "$speed bps"
                    }
                }
            }
        }
    }
    catch {
        # Network info failure shouldn't fail the whole script
        Write-Warning "Falha ao obter detalhes de rede: $_"
    }
            
    # 6. Uptime Calculation
    $uptime = @{
        uptime_days    = 0
        uptime_hours   = 0
        uptime_seconds = 0
    }
    if ($os.LastBootUpTime) {
        try {
            $bootDate = [Management.ManagementDateTimeConverter]::ToDateTime($os.LastBootUpTime)
            $uptimeSpan = (Get-Date) - $bootDate
            $uptime = @{
                uptime_days    = $uptimeSpan.Days
                uptime_hours   = $uptimeSpan.Hours
                uptime_seconds = [math]::Round($uptimeSpan.TotalSeconds)
            }
        }
        catch {}
    }
    
    # 7. Current User Detection
    $currentUser = "N/A"
    try {
        # Method 1: Console User via ComputerSystem
        if ($ram -and $ram.UserName) {
            $currentUser = $ram.UserName
        }
        # Method 2: Explorer Owner (fallback)
        else {
            $explorer = Get-WmiObject Win32_Process -Filter "Name='explorer.exe'" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($explorer) {
                $owner = $explorer.GetOwner()
                if ($owner.ReturnValue -eq 0 -and $owner.User) {
                    $currentUser = "$($owner.Domain)\$($owner.User)"
                }
            }
        }
    }
    catch {
        $currentUser = "Error"
    }
    
    # 8. TeamViewer ID Retrieval
    $tvId = "N/A"
    function Get-TeamViewerID {
        $clientId = $null
        
        # 1. Registry Search
        $registryPaths = @(
            "HKLM:\SOFTWARE\WOW6432Node\TeamViewer",
            "HKLM:\SOFTWARE\TeamViewer",
            "HKCU:\SOFTWARE\TeamViewer",
            "HKLM:\SOFTWARE\WOW6432Node\TeamViewer\Version15",
            "HKLM:\SOFTWARE\TeamViewer\Version15",
            "HKLM:\SOFTWARE\WOW6432Node\TeamViewer\Version14",
            "HKLM:\SOFTWARE\TeamViewer\Version14",
            "HKLM:\SOFTWARE\WOW6432Node\TeamViewer\Version13",
            "HKLM:\SOFTWARE\TeamViewer\Version13",
            "HKLM:\SOFTWARE\WOW6432Node\TeamViewer\Version12",
            "HKLM:\SOFTWARE\TeamViewer\Version12"
        )
                
        foreach ($path in $registryPaths) {
            if (Test-Path -Path $path -ErrorAction SilentlyContinue) {
                $regItem = Get-ItemProperty -Path $path -Name "ClientID" -ErrorAction SilentlyContinue
                if ($regItem -and $regItem.ClientID) {
                    return $regItem.ClientID.ToString()
                }
            }
        }
                
        # 2. Log File Search
        $logPaths = @(
            "$env:ProgramFiles\TeamViewer\TeamViewer.log",
            "${env:ProgramFiles(x86)}\TeamViewer\TeamViewer.log",
            "$env:ProgramData\TeamViewer\TeamViewer.log"
        )
                
        foreach ($logPath in $logPaths) {
            if (Test-Path -Path $logPath -ErrorAction SilentlyContinue) {
                try {
                    $content = Get-Content -Path $logPath -Tail 1000 -ErrorAction SilentlyContinue
                    foreach ($line in $content) {
                        if ($line -match "ClientID:\s*(\d{9,})") {
                            return $matches[1]
                        }
                    }
                }
                catch {}
            }
        }
        return "N/A"
    }
    try { $tvId = Get-TeamViewerID } catch {}
    
    $result = @{
        OS             = $osInfo.OS
        OS_Version     = $osInfo.OS_Version
        InstallDate    = $osInfo.InstallDate
        LastBootUpTime = $osInfo.LastBootUpTime
        CPU            = $cpuInfo
        RAM_GB         = $ramGB
        Disks          = $disks
        SubnetMask     = $networkInfo.SubnetMask
        Gateway        = $networkInfo.Gateway
        DNSServers     = $networkInfo.DNSServers
        DHCPServer     = $networkInfo.DHCPServer
        Interface      = $networkInfo.Interface
        LinkSpeed      = $networkInfo.LinkSpeed
        MACAddress     = $networkInfo.MACAddress
        Uptime         = $uptime
        CurrentUser    = $currentUser
        TeamViewerID   = $tvId
        Domain         = $domain
    }
            
    $result | ConvertTo-Json -Depth 3 -Compress
}
catch {
    $errObj = @{
        error      = $_.Exception.Message
        full_error = $_.ToString()
    }
    $errObj | ConvertTo-Json -Compress
}
