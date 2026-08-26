# Write-Host "=== Listando usuários conectados (Agregado) ==="
$script:uniqueUsers = @{}

# Função auxiliar para adicionar usuário se não existir
function Add-User {
    param ($uObj)
    if ($uObj -and $uObj.SessionId) {
        if (-not $script:uniqueUsers.ContainsKey($uObj.SessionId)) {
            $script:uniqueUsers[$uObj.SessionId] = $uObj
            # Write-Host "Adicionado: $($uObj.UserName) (ID: $($uObj.SessionId)) via $($uObj.Source)"
        }
    }
}

# Função auxiliar para parsear linha de texto (query user/quser)
function Parse-UserLine {
    param ($line, $source)
    
    # Remover marcador de usuário atual
    if ($line.StartsWith('>')) { $line = $line.Substring(1) }
    
    # Dividir por whitespace
    $parts = $line -split '\s+' | Where-Object { $_ -ne '' }
    
    if ($parts.Count -ge 3) {
        $uName = $parts[0]
        $sId = $null
        $sState = $null
        $sName = ""
        $logonTime = $null
        $idleTime = $null
        
        # Estratégia de detecção baseada na coluna numérica (ID)
        # Caso 1: USERNAME ID STATE IDLE TIME LOGON TIME (SessionName vazio)
        if ($parts[1] -match '^\d+$') {
            $sId = $parts[1]
            $sState = $parts[2]
            $sName = "" 
            if ($parts.Count -ge 5) { $idleTime = $parts[3] }
            if ($parts.Count -ge 6) { $logonTime = $parts[4..($parts.Count - 1)] -join ' ' }
        }
        # Caso 2: USERNAME SESSIONNAME ID STATE IDLE TIME LOGON TIME
        elseif ($parts.Count -ge 4 -and $parts[2] -match '^\d+$') {
            $sName = $parts[1]
            $sId = $parts[2]
            $sState = $parts[3]
            if ($parts.Count -ge 6) { $idleTime = $parts[4] }
            if ($parts.Count -ge 7) { $logonTime = $parts[5..($parts.Count - 1)] -join ' ' }
        }
        
        if ($sId) {
            $duration = "N/A"
            $preciseLogonDate = $null

            # Tentar obter LogonTime preciso via processo winlogon.exe da sessão
            try {
                $winlogon = Get-WmiObject -Class Win32_Process -Filter "Name='winlogon.exe' AND SessionId=$sId" | Select-Object -First 1
                if ($winlogon -and $winlogon.CreationDate) {
                    $preciseLogonDate = [System.Management.ManagementDateTimeConverter]::ToDateTime($winlogon.CreationDate)
                    # Write-Host "DEBUG: Found winlogon for session $sId, time: $preciseLogonDate"
                }
            }
            catch {
                # Write-Host "DEBUG: Failed to get winlogon for session $sId: $_"
            }

            # Se falhou winlogon, tentar Win32_LogonSession (menos confiável pois ID de logon != SessionID)
            # Mas podemos tentar correlacionar via Win32_LoggedOnUser -> Win32_Session -> Win32_LogonSession (complexo)
            # Simplificação: Se winlogon falhar, tentar parsear o texto do quser (com risco de formato de data)
            
            if (-not $preciseLogonDate -and $logonTime -and $logonTime -ne "N/A") {
                try {
                    # Tentar parsear data do quser (formato local)
                    $preciseLogonDate = [DateTime]::Parse($logonTime)
                }
                catch {}
            }

            if ($preciseLogonDate) {
                $span = (Get-Date) - $preciseLogonDate
                $duration = "{0:dd}d {0:hh}h {0:mm}m" -f $span
                # Formatar para exibição consistente
                $logonTime = $preciseLogonDate.ToString("g")
            }

            return [PSCustomObject]@{
                UserName    = $uName
                SessionId   = "$sId"
                State       = $sState
                SessionName = $sName
                Source      = $source
                LogonTime   = $logonTime
                IdleTime    = $idleTime
                Duration    = $duration
            }
        }
    }
    return $null
}

# 1. Tentar Processo Explorer (PRIORIDADE MÁXIMA)
# Identifica o dono do processo explorer.exe, que é o usuário real da sessão interativa.
# Isso evita erros de parsing do comando 'quser' que podem truncar nomes ou errar colunas.
try {
    $explorers = Get-WmiObject -Class Win32_Process -Filter "Name='explorer.exe'"
    foreach ($exp in $explorers) {
        $owner = $exp.GetOwner()
        if ($owner.ReturnValue -eq 0 -and $owner.User) {
            $sIdStr = "$($exp.SessionId)"
            
            # Formatar data de criação do explorer como tempo de logon (aproximado e confiável)
            $logonTimeStr = "N/A"
            $durationStr = "N/A"
            try {
                if ($exp.CreationDate) {
                    $cDate = [System.Management.ManagementDateTimeConverter]::ToDateTime($exp.CreationDate)
                    $logonTimeStr = $cDate.ToString("g")
                    $span = (Get-Date) - $cDate
                    $durationStr = "{0:dd}d {0:hh}h {0:mm}m" -f $span
                }
            }
            catch {}

            $u = [PSCustomObject]@{
                UserName    = $owner.User
                SessionId   = $sIdStr
                State       = "Active"
                SessionName = "Console" # Assumir console/ativo para explorer.exe
                Source      = "Process_Explorer"
                LogonTime   = $logonTimeStr
                IdleTime    = "."
                Duration    = $durationStr
            }
            Add-User -uObj $u
        }
    }
}
catch { 
    # Write-Host "Erro em Process Explorer: $_" 
}

# 2. Tentar Win32_ComputerSystem (Usuário logado no console físico)
try {
    $cs = Get-WmiObject -Class Win32_ComputerSystem
    if ($cs.UserName) {
        $domain, $user = $cs.UserName.Split('\\')
        if (-not $user) { $user = $domain }
        
        # Verificar se este usuário já foi encontrado (por exemplo, via Explorer com ID numérico)
        $alreadyFound = $false
        foreach ($existing in $script:uniqueUsers.Values) {
            if ($existing.UserName -eq $user) {
                $alreadyFound = $true
                break
            }
        }

        if (-not $alreadyFound) {
            $isValid = $true
            # Validação extra para evitar falsos positivos do WinRM
            # Removed check that excluded current user ($env:USERNAME) to support local execution usage
            # if ($user -eq $env:USERNAME) {
            #    $isValid = $false 
            # }

            if ($isValid) {
                $u = [PSCustomObject]@{
                    UserName    = $user
                    SessionId   = "Console"
                    State       = "Active"
                    SessionName = "Console"
                    Source      = "WMI_ComputerSystem"
                    LogonTime   = "N/A"
                    IdleTime    = "N/A"
                    Duration    = "N/A"
                }
                Add-User -uObj $u
            }
        }
    }
}
catch { 
    # Write-Host "Erro em WMI (ComputerSystem): $_" 
}

# 3. Tentar WMI (Win32_LogonSession) - Complementar
try {
    $sessions = Get-WmiObject -Class Win32_LogonSession | Where-Object { $_.LogonType -eq 2 -or $_.LogonType -eq 10 }
    foreach ($session in $sessions) {
        $user = Get-WmiObject -Class Win32_LoggedOnUser | Where-Object { $_.Dependent.LogonId -eq $session.LogonId }
        if ($user) {
            $account = Get-WmiObject -Class Win32_Account | Where-Object { $_.SID -eq $user.Antecedent.SID }
            if ($account -and $account.Name -notmatch 'SYSTEM|SERVICE') {
                $u = [PSCustomObject]@{
                    UserName    = $account.Name
                    SessionId   = "$($session.LogonId)"
                    State       = "Active"
                    SessionName = "WMI"
                    Source      = "WMI_LogonSession"
                    LogonTime   = "N/A"
                    IdleTime    = "N/A"
                    Duration    = "N/A"
                }
                Add-User -uObj $u
            }
        }
    }
}
catch { 
    # Write-Host "Erro em WMI (LogonSession): $_" 
}

# 4. Tentar query user (Fallback - Baixa prioridade)
try {
    $queryOutput = query user 2>$null
    if ($queryOutput) {
        $queryOutput | Select-Object -Skip 1 | ForEach-Object {
            $u = Parse-UserLine -line $_.Trim() -source "query_user"
            Add-User -uObj $u
        }
    }
}
catch {}

# 5. Tentar quser (Fallback redundante)
try {
    $quserOutput = quser 2>$null
    if ($quserOutput) {
        $quserOutput | Select-Object -Skip 1 | ForEach-Object {
            $u = Parse-UserLine -line $_.Trim() -source "quser"
            Add-User -uObj $u
        }
    }
}
catch {}

# Converter hashtable para array
# Write-Host "DEBUG: UniqueUsers Count before sort: $($script:uniqueUsers.Count)"
$finalUsers = @($script:uniqueUsers.Values | Sort-Object SessionId)

# Write-Host "Total de usuários únicos encontrados: $($finalUsers.Count)"

if ($finalUsers.Count -gt 0) {
    Write-Output "=== RESULTADO_JSON_INICIO ==="
    $finalUsers | ConvertTo-Json -Depth 2 -Compress
    Write-Output "=== RESULTADO_JSON_FIM ==="
}
else {
    Write-Output "=== RESULTADO_JSON_INICIO ==="
    Write-Output "[]"
    Write-Output "=== RESULTADO_JSON_FIM ==="
}
