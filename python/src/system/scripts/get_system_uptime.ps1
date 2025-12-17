
$ErrorActionPreference = "SilentlyContinue"

try {
    # Obter tempo de boot usando WMI
    $os = Get-WmiObject -Class Win32_OperatingSystem
    if ($os -and $os.LastBootUpTime) {
        $bootTime = [Management.ManagementDateTimeConverter]::ToDateTime($os.LastBootUpTime)
        $bootTimeIso = $bootTime.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")

        # Calcular uptime atual
        $uptime = (Get-Date) - $bootTime
        $uptimeSeconds = [math]::Floor($uptime.TotalSeconds)

        # Informações adicionais do sistema
        $computerInfo = Get-ComputerInfo -Property TotalPhysicalMemory, CsProcessors 2>$null

        $result = @{
            boot_time      = $bootTimeIso
            uptime_seconds = $uptimeSeconds
            uptime_days    = [math]::Floor($uptime.TotalDays)
            uptime_hours   = [math]::Floor($uptime.TotalHours)
            current_time   = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
            computer_name  = $env:COMPUTERNAME
        }

        if ($computerInfo) {
            $result.total_memory_gb = [math]::Round($computerInfo.TotalPhysicalMemory / 1GB, 2)
            $result.processor_count = $computerInfo.CsProcessors.Count
        }

        # Converter para JSON
        $json = $result | ConvertTo-Json -Compress
        Write-Output $json
    }
    else {
        Write-Output '{"error": "Não foi possível obter informações de boot do sistema"}'
    }
}
catch {
    $errorMsg = $_.Exception.Message
    Write-Output "{`"error`": `"Erro ao obter uptime: $errorMsg`"}"
}
