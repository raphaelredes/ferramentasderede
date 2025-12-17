
try {
    # Verificar se o log existe
    $logExists = Get-WinEvent -ListLog '__LOG_NAME__' -ErrorAction SilentlyContinue
    if (-not $logExists) {
        Write-Output "LOG_NOT_FOUND"
        return
    }
            
    # Tentar buscar eventos com o filtro específico
    $events = Get-WinEvent -LogName '__LOG_NAME__' -FilterXPath "*[System/Level=__LEVEL_ID__]" -MaxEvents __COUNT__ -ErrorAction SilentlyContinue
            
    if ($events -and $events.Count -gt 0) {
        $events | ForEach-Object {
            [PSCustomObject]@{
                TimeCreated      = $_.TimeCreated.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                Id               = $_.Id
                LevelDisplayName = $_.LevelDisplayName
                ProviderName     = $_.ProviderName
                Message          = $_.Message
            }
        } | ConvertTo-Json -Compress -Depth 3
    }
    else {
        # Se não encontrou com filtro específico, tentar sem filtro para ver se há logs
        $allEvents = Get-WinEvent -LogName '__LOG_NAME__' -MaxEvents 5 -ErrorAction SilentlyContinue
        if ($allEvents -and $allEvents.Count -gt 0) {
            Write-Output "NO_LEVEL_MATCH"
        }
        else {
            Write-Output "[]"
        }
    }
}
catch {
    Write-Output "ERROR: $($_.Exception.Message)"
}
