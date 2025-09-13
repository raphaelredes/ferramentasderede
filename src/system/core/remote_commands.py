# src/ferramentasderede/system/core/remote_commands.py
# Gerencia a sessão WinRM e executa comandos de alto nível.

import json
import re
import time
import logging
from .winrm_handler import WinRMHandler, WinRMError, ConnectionError, ConnectTimeout

class RemoteCommands:
    def __init__(self, target_ip, username, password):
        self.target_ip = target_ip
        self.username = username
        self.password = password
        self.handler = None

    def __enter__(self):
        """Permite o uso em um 'with' statement, estabelecendo a conexão."""
        import logging
        try:
            self.handler = WinRMHandler(self.target_ip, self.username, self.password)
            connection_result = self.handler.connect()
            if "error" in connection_result:
                # Propaga a exceção original para ser capturada pelo helper
                logging.error(f"WinRM connection failed for {self.target_ip}: {connection_result['error']}")
                raise ConnectionError(connection_result['error'])
            return self
        except Exception as e:
            logging.error(f"Erro em __enter__ do RemoteCommands: {type(e).__name__} - {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Garante que a conexão seja fechada ao sair do 'with'."""
        if self.handler:
            self.handler.close()
            
    def check_winrm_status(self):
        """
        Executa um comando leve para verificar se o serviço WinRM está respondendo.
        Retorna True em caso de sucesso, False em caso de falha.
        """
        return True

    def list_connected_users_winrm(self):
        logging.info(f"Executing 'list_connected_users_winrm' on {self.target_ip}")
        """Executa 'qwinsta' (alias de query session) no host remoto e parseia a saída."""
        script = "qwinsta"
        result = self.handler.execute_script(script)
        logging.debug(f"Raw output for qwinsta: {result.get('output')}")
        
        output = "\n".join(result.get("output", []))
        yield output + "\n", []

        parsed_users = []
        users_raw = output.strip().split('\n')
        if len(users_raw) > 1:
            for line in users_raw[1:]:
                line = line.lstrip('>')
                parts = re.split(r'\s{2,}', line.strip())
                if len(parts) < 4: continue
                
                username, session_id, state = parts[1], parts[2], parts[3]
                
                if username and username != '-' and session_id.isdigit():
                    state_normalized = 'Ativo' if state.lower() in ['ativo', 'active', 'activ'] else state.capitalize()
                    logging.debug(f"Found user session: User={username}, ID={session_id}, State={state_normalized}")
                    parsed_users.append({'UserName': username, 'ID': session_id, 'State': state_normalized})
        
        logging.info(f"Finished 'list_connected_users_winrm' on {self.target_ip}. Found {len(parsed_users)} sessions.")
        yield "", parsed_users

    def disconnect_user_winrm(self, session_id):
        logging.info(f"Executing 'disconnect_user_winrm' for session ID {session_id} on {self.target_ip}")
        """Executa 'logoff' no host remoto e depois atualiza a lista."""
        script = f"logoff {session_id}"
        logging.debug(f"Executing logoff script: {script}")
        result = self.handler.execute_script(script)
        
        output = "\n".join(result.get("output", []))
        yield f"Comando 'logoff {session_id}' enviado.\n{output}\n", None
        
        time.sleep(2)
        yield "Atualizando lista de usuários...\n", None
        yield from self.list_connected_users_winrm()

    def get_user_activity_events(self, start_time, end_time):
        logging.info(f"Executing 'get_user_activity_events' on {self.target_ip} for period {start_time} to {end_time}")
        """Busca eventos de atividade usando múltiplas fontes de dados com fallbacks robustos."""
        script = f"""
        $ErrorActionPreference = "SilentlyContinue"
        $start = Get-Date -Date '{start_time}'
        $end = Get-Date -Date '{end_time}'
        
        # Função para obter eventos de segurança (método principal)
        function Get-SecurityEvents {{
            try {{
                $auditPolicy = auditpol /get /subcategory:"Logon" 2>$null
                if (($auditPolicy -notlike "*Success and Failure*") -and ($auditPolicy -notlike "*Sucesso e Falha*")) {{
                    return $null
                }}
                
                $eventIds = @(4624, 4634, 4647, 4800, 4801, 4778, 4779)
                $filter = @{{
                    LogName = 'Security'
                    ID = $eventIds
                    StartTime = $start
                    EndTime = $end
                }}
                $events = Get-WinEvent -FilterHashtable $filter -ErrorAction SilentlyContinue
                
                $results = foreach ($event in $events) {{
                    $eventType = "Unknown"
                    if ($event.Id -eq 4624) {{
                        $logonType = ($event.Properties[8].Value)
                        if ($logonType -in @(2, 10)) {{ $eventType = "Logon" }} else {{ continue }}
                    }} elseif ($event.Id -in @(4634, 4647)) {{ $eventType = "Logoff" }}
                    elseif ($event.Id -eq 4800) {{ $eventType = "Lock" }}
                    elseif ($event.Id -eq 4801) {{ $eventType = "Unlock" }}
                    elseif ($event.Id -eq 4778) {{ $eventType = "Reconnect" }}
                    elseif ($event.Id -eq 4779) {{ $eventType = "Disconnect" }}
                    [PSCustomObject]@{{
                        Time = $event.TimeCreated.ToUniversalTime().ToString("o")
                        Type = $eventType
                        User = $event.Properties[5].Value
                        Source = "Security"
                    }}
                }}
                return $results
            }} catch {{
                return $null
            }}
        }}
        
        # Função para obter eventos do sistema (fallback)
        function Get-SystemEvents {{
            try {{
                $eventIds = @(7001, 7002, 1074, 1076, 6005, 6006, 6008)
                $filter = @{{
                    LogName = 'System'
                    ID = $eventIds
                    StartTime = $start
                    EndTime = $end
                }}
                $events = Get-WinEvent -FilterHashtable $filter -ErrorAction SilentlyContinue
                
                $results = foreach ($event in $events) {{
                    $eventType = "Unknown"
                    if ($event.Id -eq 7001) {{ $eventType = "Logon" }}
                    elseif ($event.Id -eq 7002) {{ $eventType = "Logoff" }}
                    elseif ($event.Id -eq 1074) {{ $eventType = "Shutdown" }}
                    elseif ($event.Id -eq 6005) {{ $eventType = "Boot" }}
                    elseif ($event.Id -eq 6006) {{ $eventType = "Shutdown" }}
                    elseif ($event.Id -eq 6008) {{ $eventType = "UnexpectedShutdown" }}
                    
                    [PSCustomObject]@{{
                        Time = $event.TimeCreated.ToUniversalTime().ToString("o")
                        Type = $eventType
                        User = "SYSTEM"
                        Source = "System"
                    }}
                }}
                return $results
            }} catch {{
                return $null
            }}
        }}
        
        # Função para obter informações de sessão atual (método alternativo)
        function Get-CurrentSessionInfo {{
            try {{
                $sessions = quser 2>$null
                if ($sessions -and $sessions -notlike "*No users*") {{
                    $currentUser = ($sessions -split '\\s+')[0]
                    $currentTime = Get-Date
                    return @{{
                        Time = $currentTime.ToUniversalTime().ToString("o")
                        Type = "CurrentSession"
                        User = $currentUser
                        Source = "Session"
                    }}
                }}
                return $null
            }} catch {{
                return $null
            }}
        }}
        
        # Função para obter informações de processos ativos (método adicional)
        function Get-ProcessActivity {{
            try {{
                # Verificar se há usuários logados
                $sessions = quser 2>$null
                if ($sessions -and $sessions -notlike "*No users*") {{
                    # Verificar processos de interação do usuário
                    $interactiveProcesses = Get-Process | Where-Object {{ 
                        $_.ProcessName -in @('explorer', 'winlogon', 'userinit', 'conhost', 'dwm') -and 
                        $_.MainWindowTitle -ne "" 
                    }}
                    
                    # Verificar atividade de mouse/teclado (aproximação)
                    $lastInput = Get-WmiObject -Class Win32_ComputerSystem | Select-Object -ExpandProperty LastBootUpTime
                    $currentTime = Get-Date
                    
                    if ($interactiveProcesses -or $lastInput) {{
                        return @{{
                            Time = $currentTime.ToUniversalTime().ToString("o")
                            Type = "ProcessActivity"
                            User = "Active"
                            Source = "Process"
                        }}
                    }}
                }}
                return $null
            }} catch {{
                return $null
            }}
        }}
        
        # Tentar métodos em ordem de prioridade
        $allEvents = @()
        
        # 1. Eventos de segurança (método principal)
        $securityEvents = Get-SecurityEvents
        if ($securityEvents) {{
            $allEvents += $securityEvents
        }}
        
        # 2. Eventos do sistema (fallback)
        $systemEvents = Get-SystemEvents
        if ($systemEvents) {{
            $allEvents += $systemEvents
        }}
        
        # 3. Informações de sessão atual
        $sessionInfo = Get-CurrentSessionInfo
        if ($sessionInfo) {{
            $allEvents += [PSCustomObject]$sessionInfo
        }}
        
        # 4. Informações de processos ativos
        $processInfo = Get-ProcessActivity
        if ($processInfo) {{
            $allEvents += [PSCustomObject]$processInfo
        }}
        
        # Se não encontrou nenhum evento, tentar método de última instância
        if ($allEvents.Count -eq 0) {{
            try {{
                # Verificar se há usuários logados
                $loggedUsers = quser 2>$null
                if ($loggedUsers -and $loggedUsers -notlike "*No users*") {{
                    # Verificar se há atividade real (mouse/teclado)
                    $lastInput = Get-WmiObject -Class Win32_ComputerSystem | Select-Object -ExpandProperty LastBootUpTime
                    $currentTime = Get-Date
                    
                    # Verificar processos interativos
                    $interactiveProcesses = Get-Process | Where-Object {{ 
                        $_.ProcessName -in @('explorer', 'winlogon', 'userinit', 'conhost', 'dwm') -and 
                        $_.MainWindowTitle -ne "" 
                    }}
                    
                    if ($interactiveProcesses) {{
                        $allEvents += [PSCustomObject]@{{
                            Time = $currentTime.ToUniversalTime().ToString("o")
                            Type = "ActiveSession"
                            User = "Detected"
                            Source = "LastResort"
                        }}
                    }} else {{
                        # Se não há processos interativos, considerar como ocioso
                        $allEvents += [PSCustomObject]@{{
                            Time = $currentTime.ToUniversalTime().ToString("o")
                            Type = "IdleSession"
                            User = "Idle"
                            Source = "LastResort"
                        }}
                    }}
                }} else {{
                    # Se não há usuários logados, considerar como ocioso
                    $currentTime = Get-Date
                    $allEvents += [PSCustomObject]@{{
                        Time = $currentTime.ToUniversalTime().ToString("o")
                        Type = "NoUsers"
                        User = "None"
                        Source = "LastResort"
                    }}
                }}
            }} catch {{
                # Ignorar erros neste método
            }}
        }}
        
        # Retornar resultado
        if ($allEvents.Count -eq 0) {{
            $result = @{{
                "error" = "Não foi possível determinar a atividade do sistema. Verifique se: 1) A política de auditoria está habilitada, 2) O usuário tem permissões adequadas, 3) O sistema está funcionando normalmente."
            }}
            return $result | ConvertTo-Json -Compress
        }}
        
        $allEvents | Sort-Object Time | ConvertTo-Json -Compress
        """
        result = self.handler.execute_script(script)
        logging.debug(f"Raw output for get_user_activity_events: {result.get('output')}")
        full_json_str = "".join(result.get("output", []))
        if not full_json_str:
            logging.warning(f"No output received for get_user_activity_events on {self.target_ip}")
            yield {"error": "no_output"}
            return
        try:
            event_list = json.loads(full_json_str)
            if isinstance(event_list, dict) and "error" in event_list:
                logging.warning(f"Remote error reported for get_user_activity_events on {self.target_ip}: {event_list.get('error')}")
                yield event_list
            else:
                logging.info(f"Successfully retrieved {len(event_list) if isinstance(event_list, list) else 1} activity events from {self.target_ip}")
                yield [event_list] if isinstance(event_list, dict) else event_list
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error for get_user_activity_events on {self.target_ip}: {e}. Raw output: {full_json_str}")
            yield {"error": "json_decode"}

    def get_teamviewer_id(self):
        logging.info(f"Executing 'get_teamviewer_id' on {self.target_ip}")
        reg_paths = [r"HKLM:\SOFTWARE\WOW6432Node\TeamViewer", r"HKLM:\SOFTWARE\TeamViewer", r"HKCU:\SOFTWARE\TeamViewer"]
        script = f"""
        $clientId = $null;
        $paths = @({','.join([f"'{p}'" for p in reg_paths])});
        foreach ($path in $paths) {{
            $clientId = (Get-ItemProperty -Path $path -Name ClientID -ErrorAction SilentlyContinue).ClientID;
            if ($clientId) {{ return $clientId; }}
        }};
        return $null;
        """
        result = self.handler.execute_script(script)
        logging.debug(f"Raw output for get_teamviewer_id: {result.get('output')}")
        output = result.get("output", [])
        if output and output[0] is not None:
            logging.info(f"TeamViewer ID found for {self.target_ip}: {output[0]}")
            yield f"SUCESSO: TeamViewer ID encontrado: {str(output[0])}\n", str(output[0])
        else:
            logging.warning(f"TeamViewer ClientID not found for {self.target_ip}")
            yield "FALHA: ClientID não foi encontrado no registro.\n", "N/A"

    def get_system_info_raw(self):
        """Agrega várias chamadas de informações do sistema para formar um único dicionário."""
        data = {}
        info_tasks = {
            "OS": self.get_os_info,
            "CPU": self.get_cpu_info,
            "RAM_GB": self.get_ram_info,
            "Disks": self.get_disks_info,
            "LastBootUpTime": self.get_last_boot_time,
            "SubnetMask": self.get_subnet_mask
        }

        for key, task in info_tasks.items():
            try:
                logging.info(f"SYSINFO: Iniciando tarefa '{key}'...")
                result = task()
                logging.info(f"SYSINFO: Tarefa '{key}' retornou: {result}")
                logging.info(f"SYSINFO: Tipo do resultado para '{key}': {type(result)}")
                if isinstance(result, dict) and not "error" in result:
                    data.update(result)
                    logging.info(f"SYSINFO: Dados atualizados com resultado de '{key}' (dict)")
                elif not isinstance(result, dict):
                    data[key] = result
                    logging.info(f"SYSINFO: Dados atualizados com resultado de '{key}' (direto): {result}")
                else:
                    error_message = result.get('error', 'Erro desconhecido')
                    logging.warning(f"SYSINFO: Error getting '{key}' from {self.target_ip}: {error_message}")
                    if key == "Disks":
                        data[key] = [] # Retorna lista vazia para Disks em caso de erro
                    else:
                        data[key] = "Erro" # Mantém 'Erro' para outros tipos
            except Exception as e:
                logging.error(f"SYSINFO: Exception getting '{key}' from {self.target_ip}: {e}", exc_info=True)
                if key == "Disks":
                    data[key] = [] # Retorna lista vazia para Disks em caso de exceção
                else:
                    data[key] = "Erro" # Mantém 'Erro' para outros tipos
        
        logging.info(f"SYSINFO: Dados finais agregados para {self.target_ip}: {data}")
        logging.info(f"SYSINFO: Discos nos dados finais: {data.get('Disks', 'NÃO ENCONTRADO')}")
        return data

    def _execute_ps_and_load_json(self, script):
        import logging
        logging.debug(f"Executando script PowerShell: {script}")
        result = self.handler.execute_script(script)
        output_list = result.get("output", [])
        logging.debug(f"Saída bruta do PowerShell: {output_list}")
        if not output_list:
            logging.warning("Nenhuma saída recebida do host para o script.")
            return {"error": "Nenhuma saída recebida do host."}
        try:
            json_data = json.loads("".join(output_list))
            logging.debug(f"JSON decodificado: {json_data}")
            return json_data
        except json.JSONDecodeError:
            logging.error(f"Falha ao decodificar JSON para o script. Saída: {"".join(output_list)}")
            return {"error": "Falha ao decodificar JSON."}

    def get_os_info(self):
        import logging
        logging.debug(f"Executando get_os_info em {self.target_ip}")
        script = "Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object Caption, Version, InstallDate | ConvertTo-Json -Compress"
        data = self._execute_ps_and_load_json(script)
        if "error" in data: return data
        return {
            "OS": data.get("Caption", "N/A"),
            "OS_Version": data.get("Version", "N/A"),
            "OS_InstallDate": data.get("InstallDate", ""),
        }

    def get_cpu_info(self):
        import logging
        logging.debug(f"Executando get_cpu_info em {self.target_ip}")
        script = "Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1 -ExpandProperty Name | ConvertTo-Json -Compress"
        data = self._execute_ps_and_load_json(script)
        return data if not "error" in data else "N/A"

    def get_ram_info(self):
        import logging
        logging.debug(f"Executando get_ram_info em {self.target_ip}")
        script = "$mem = Get-CimInstance -ClassName Win32_PhysicalMemory; [Math]::Round(($mem | Measure-Object -Property Capacity -Sum).Sum / 1GB)"
        result = self.handler.execute_script(script)
        output = result.get("output", [])
        logging.debug(f"Saída bruta do PowerShell para RAM: {output}") # Novo log
        if output and (isinstance(output[0], (int, float)) or (isinstance(output[0], str) and output[0].strip().isdigit())):
            return int(float(output[0]))
        elif output and isinstance(output[0], str):
            # Tenta extrair o número de uma string como '<Db>8</Db>'
            match = re.search(r'<Db>(\d+)</Db>', output[0]) # Corrigido: \d+ para escapar a barra invertida
            if match:
                return int(match.group(1))
        return 0 # Retorna 0 se não conseguir extrair ou não houver saída

    def get_disks_info(self):
        import logging
        logging.info(f"DISKS: Executando get_disks_info em {self.target_ip}")
        script = 'Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, VolumeName, @{N="Total_GB";E={[Math]::Round($_.Size / 1GB, 2)}}, @{N="Free_GB";E={[Math]::Round($_.FreeSpace / 1GB, 2)}} | ConvertTo-Json -Compress'
        logging.info(f"DISKS: Script PowerShell: {script}")
        data = self._execute_ps_and_load_json(script)
        logging.info(f"DISKS: Dados retornados do PowerShell: {data}")
        logging.info(f"DISKS: Tipo dos dados: {type(data)}")
        if isinstance(data, dict) and "error" in data:
            logging.error(f"DISKS: Erro detectado nos dados: {data['error']}")
            return []
        elif isinstance(data, list):
            logging.info(f"DISKS: Lista de discos retornada com {len(data)} itens")
            return data
        elif isinstance(data, dict):
            logging.info("DISKS: Dados em formato de dicionário, convertendo para lista")
            return [data]  # Se for apenas um disco, converter para lista
        else:
            logging.warning(f"DISKS: Formato inesperado dos dados: {type(data)} - {data}")
            return []

    def get_last_boot_time(self):
        import logging
        logging.debug(f"Executando get_last_boot_time em {self.target_ip}")
        script = "(Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime.ToString('o')"
        result = self.handler.execute_script(script)
        return result.get("output", ["N/A"])[0]

    def get_subnet_mask(self):
        import logging
        logging.debug(f"Executando get_subnet_mask em {self.target_ip}")
        script = "(Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration -Filter \"IPEnabled = 'true'\" | Select-Object -First 1).IPSubnet[0]"
        result = self.handler.execute_script(script)
        return result.get("output", ["N/A"])[0]

    def execute_shutdown_command(self, action_flag, message, delay_seconds):
        logging.info(f"Executing shutdown command ({action_flag}) on {self.target_ip} with delay {delay_seconds}s")
        sanitized_message = message.replace("'", "''") if message else ""
        script = f"shutdown.exe {action_flag} /f /t {int(delay_seconds)}"
        if sanitized_message:
            script += f" /c '{sanitized_message}'"
        logging.debug(f"Shutdown script: {script}")
        result = self.handler.execute_script(script)

        if result.get("success"):
            logging.info(f"Shutdown command executed successfully on {self.target_ip}")
            yield f"Comando '{script}' enviado com sucesso.\n"
        else:
            logging.error(f"Failed to execute shutdown command on {self.target_ip}. Output: {result.get('output')}, Error: {result.get('error')}")
            yield f"Falha ao enviar comando \'{script}\'.\\n{result.get('error', '')}\\n\""
    def get_remote_services(self):
        script = "Get-Service | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json -Compress"
        result = self.handler.execute_script(script)
        output_list = result.get("output", [])
        if output_list:
            try:
                return json.loads("".join(output_list))
            except json.JSONDecodeError:
                logging.error(f"JSON decode error for get_remote_services on {self.target_ip}. Raw output: {"".join(output_list)}")
                return {"error": "Falha ao decodificar a lista de serviços."}
        logging.warning(f"No output received for get_remote_services on {self.target_ip}.")
        return {"error": "Nenhuma saída de serviços recebida."}

    def get_single_service(self, service_name):
        logging.debug(f"Getting info for service '{service_name}' on {self.target_ip}")
        script = f"Get-Service -Name '{service_name}' | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json -Compress"
        logging.debug(f"Script for single service: {script}")
        result = self.handler.execute_script(script)
        output_list = result.get("output", [])
        if output_list:
            try:
                return json.loads("".join(output_list))
            except json.JSONDecodeError:
                return {"error": "Falha ao decodificar o serviço."}
        logging.warning(f"No output received for single service '{service_name}' on {self.target_ip}.")
        return {"error": f"Serviço '{service_name}' não encontrado."}

    def manage_remote_service(self, service_name, action):
        logging.info(f"Attempting to '{action}' service '{service_name}' on {self.target_ip}")
        action_map = {"start": "Start-Service", "stop": "Stop-Service", "restart": "Restart-Service"}
        command = action_map.get(action.lower())
        if not command:
            logging.warning(f"Invalid service action '{action}' requested for '{service_name}' on {self.target_ip}")
            yield f"Ação '{action}' inválida."
            return
        script = f"Get-Service -Name '{service_name}' | {command}"
        logging.debug(f"Service management script: {script}")
        self.handler.execute_script(script)
        logging.info(f"Command to '{action}' service '{service_name}' sent to {self.target_ip}")
        yield f"Comando para '{action}' o serviço '{service_name}' enviado."

    def get_remote_event_logs(self, log_name, level, count):
        level_map = {"Error": 2, "Warning": 3, "Information": 4}
        level_id = level_map.get(level, 0)
        
        # Script PowerShell melhorado com debug e verificação de logs disponíveis
        script = f"""
        try {{
            # Verificar se o log existe
            $logExists = Get-WinEvent -ListLog '{log_name}' -ErrorAction SilentlyContinue
            if (-not $logExists) {{
                Write-Output "LOG_NOT_FOUND"
                return
            }}
            
            # Tentar buscar eventos com o filtro específico
            $events = Get-WinEvent -LogName '{log_name}' -FilterXPath "*[System/Level={level_id}]" -MaxEvents {count} -ErrorAction SilentlyContinue
            
            if ($events -and $events.Count -gt 0) {{
                $events | ForEach-Object {{
                    [PSCustomObject]@{{
                        TimeCreated = $_.TimeCreated.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                        Id = $_.Id
                        LevelDisplayName = $_.LevelDisplayName
                        ProviderName = $_.ProviderName
                        Message = $_.Message
                    }}
                }} | ConvertTo-Json -Compress -Depth 3
            }} else {{
                # Se não encontrou com filtro específico, tentar sem filtro para ver se há logs
                $allEvents = Get-WinEvent -LogName '{log_name}' -MaxEvents 5 -ErrorAction SilentlyContinue
                if ($allEvents -and $allEvents.Count -gt 0) {{
                    Write-Output "NO_LEVEL_MATCH"
                }} else {{
                    Write-Output "[]"
                }}
            }}
        }} catch {{
            Write-Output "ERROR: $($_.Exception.Message)"
        }}
        """
        
        result = self.handler.execute_script(script)
        output_list = result.get("output", [])
        logging.debug(f"Raw output for get_remote_event_logs ({log_name}, level {level}, count {count}) on {self.target_ip}: {output_list}")

        if not output_list:
            logging.warning(f"No output received for event logs from {self.target_ip}")
            return []

        full_json_str = "".join(output_list).strip()
        
        # Verificar casos especiais
        if full_json_str == "LOG_NOT_FOUND":
            logging.warning(f"Log '{log_name}' not found on {self.target_ip}")
            return [{"error": f"Log '{log_name}' não encontrado no host remoto."}]
        elif full_json_str == "NO_LEVEL_MATCH":
            logging.info(f"No events with level {level} found in log '{log_name}' on {self.target_ip}")
            return [{"error": f"Nenhum evento com nível '{level}' encontrado no log '{log_name}'."}]
        elif full_json_str.startswith("ERROR:"):
            logging.error(f"PowerShell error on {self.target_ip}: {full_json_str}")
            return [{"error": f"Erro no PowerShell: {full_json_str[6:]}"}]
        elif not full_json_str or full_json_str == "[]":
            logging.info(f"No event logs found for {log_name} with level {level} on {self.target_ip}")
            return []
            
        try:
            data = json.loads(full_json_str)
            logging.debug(f"Successfully parsed {len(data) if isinstance(data, list) else 1} event log entries from {self.target_ip}")
            
            # Garante que a saída seja sempre uma lista
            if isinstance(data, dict):
                if "error" in data:
                    logging.warning(f"Remote error getting event logs from {self.target_ip}: {data.get('error')}")
                    return []
                return [data]
            return data
        except (json.JSONDecodeError, TypeError) as e:
            logging.error(f"JSON decode error for event logs from {self.target_ip}: {e}. Raw output: {full_json_str[:200]}...")
            return []

    def get_network_interfaces_with_ips(self):
        """Retorna informações das interfaces de rede e seus IPs do host remoto.
        Saída: lista de objetos com IPs, Description, Name, NetConnectionID.
        """
        logging.info(f"Executing 'get_network_interfaces_with_ips' on {self.target_ip}")
        script = r'''
        try {
            $adapters = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled = True" 2>$null
            $result = @()
            foreach ($cfg in $adapters) {
                try {
                    $na = Get-CimInstance Win32_NetworkAdapter -Filter ("Index = {0}" -f $cfg.Index) 2>$null
                } catch {
                    $na = $null
                }
                $obj = [PSCustomObject]@{
                    IPs = $cfg.IPAddress
                    Description = $cfg.Description
                    MAC = $cfg.MACAddress
                    NetConnectionID = if ($na) { $na.NetConnectionID } else { $null }
                    AdapterType = if ($na) { $na.AdapterType } else { $null }
                    Name = if ($na) { $na.Name } else { $null }
                }
                $result += $obj
            }
            $result | ConvertTo-Json -Compress
        } catch {
            Write-Output "[]"
        }
        '''
        result = self.handler.execute_script(script)
        output_list = result.get("output", [])
        full_json_str = "".join(output_list).strip()
        if not full_json_str:
            logging.warning(f"No output for get_network_interfaces_with_ips from {self.target_ip}")
            return []
        try:
            data = json.loads(full_json_str)
            if isinstance(data, dict):
                return [data]
            return data
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error for get_network_interfaces_with_ips on {self.target_ip}: {e}. Raw: {full_json_str}")
            return []