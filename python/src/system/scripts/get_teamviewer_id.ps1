
# Função para buscar TeamViewer ID de forma robusta
function Get-TeamViewerID {
    $clientId = $null
    $found = $false
            
    # 1. Busca no Registro (Método Principal)
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
            
    # 2. Busca em Arquivos de Log (Fallback Robusto)
    $logPaths = @(
        "$env:ProgramFiles\TeamViewer\TeamViewer.log",
        "${env:ProgramFiles(x86)}\TeamViewer\TeamViewer.log",
        "$env:ProgramData\TeamViewer\TeamViewer.log"
    )
            
    foreach ($logPath in $logPaths) {
        if (Test-Path -Path $logPath -ErrorAction SilentlyContinue) {
            try {
                # Ler as últimas 1000 linhas para não ler arquivo gigante
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
            
    return $null
}
        
$tvId = Get-TeamViewerID
if ($tvId) {
    Write-Output $tvId
}
else {
    Write-Output "Unknown"
}
