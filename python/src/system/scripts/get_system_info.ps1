
$ErrorActionPreference = "SilentlyContinue"
        
# 1. OS Info
$os = Get-WmiObject Win32_OperatingSystem
$osInfo = @{
    OS             = $os.Caption
    OS_Version     = $os.Version
    LastBootUpTime = [Management.ManagementDateTimeConverter]::ToDateTime($os.LastBootUpTime).ToString("yyyy-MM-ddTHH:mm:ss")
    InstallDate    = [Management.ManagementDateTimeConverter]::ToDateTime($os.InstallDate).ToString("yyyy-MM-ddTHH:mm:ss")
}
        
# 2. CPU Info
$cpu = Get-WmiObject Win32_Processor | Select-Object -First 1
$cpuInfo = $cpu.Name
        
# 3. RAM Info
$ram = Get-WmiObject Win32_ComputerSystem
$ramGB = [math]::Round($ram.TotalPhysicalMemory / 1GB, 2)
        
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
$netConfig = Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object { $_.IPAddress -contains "__TARGET_IP__" } | Select-Object -First 1

$networkInfo = @{
    SubnetMask = "N/A"
    Gateway    = "N/A"
    DNSServers = "N/A"
    DHCPServer = "N/A"
    Interface  = "N/A"
    LinkSpeed  = "N/A"
    MACAddress = "N/A"
}

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
        
# 6. Uptime Calculation
$bootDate = [Management.ManagementDateTimeConverter]::ToDateTime($os.LastBootUpTime)
$uptimeSpan = (Get-Date) - $bootDate
$uptime = @{
    uptime_days    = $uptimeSpan.Days
    uptime_hours   = $uptimeSpan.Hours
    uptime_seconds = [math]::Round($uptimeSpan.TotalSeconds)
}

# 7. Current User Detection
$currentUser = "N/A"
try {
    # Method 1: Console User via ComputerSystem
    $cs = Get-WmiObject Win32_ComputerSystem
    if ($cs.UserName) {
        $currentUser = $cs.UserName
    }
    # Method 2: Explorer Owner (fallback)
    else {
        $explorer = Get-WmiObject Win32_Process -Filter "Name='explorer.exe'" | Select-Object -First 1
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
}
        
$result | ConvertTo-Json -Depth 3 -Compress
