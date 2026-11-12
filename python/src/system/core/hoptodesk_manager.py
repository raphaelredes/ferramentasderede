# src/system/core/hoptodesk_manager.py
# Gerenciamento de download local, verificação de versão, implantação remota
# e conexão via HopToDesk de forma segura e compatível com antivírus.

import os
import sys
import json
import time
import shutil
import logging
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Optional, Dict, Any, Generator, Tuple
import urllib.request
import urllib.error
import subprocess

try:
    from ...config.settings import APP_DATA_DIR
except Exception:
    APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FerramentasDeRede")

# Estrutura Win32 para conexão de rede autenticada (SMB / WNetAddConnection2)
class _NETRESOURCEW(ctypes.Structure):
    _fields_ = [
        ("dwScope", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("dwDisplayType", wintypes.DWORD),
        ("dwUsage", wintypes.DWORD),
        ("lpLocalName", wintypes.LPWSTR),
        ("lpRemoteName", wintypes.LPWSTR),
        ("lpComment", wintypes.LPWSTR),
        ("lpProvider", wintypes.LPWSTR),
    ]


class HopToDeskManager:
    OFFICIAL_DOWNLOAD_URL = "https://dl.hoptodesk.com/HopToDesk.exe"
    REMOTE_PUBLIC_DESKTOP_PATH = r"C:\Users\Public\Desktop\HopToDesk.exe"

    @classmethod
    def get_bin_dir(cls) -> Path:
        bin_dir = Path(APP_DATA_DIR) / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        return bin_dir

    @classmethod
    def get_local_exe_path(cls) -> Path:
        return cls.get_bin_dir() / "HopToDesk.exe"

    @classmethod
    def get_meta_path(cls) -> Path:
        return cls.get_bin_dir() / "hoptodesk_meta.json"

    @classmethod
    def check_remote_version_info(cls) -> Dict[str, Any]:
        """Consulta os cabeçalhos HTTP do servidor oficial do HopToDesk (HEAD) para verificar versão/tamanho."""
        try:
            req = urllib.request.Request(
                cls.OFFICIAL_DOWNLOAD_URL,
                method="HEAD",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=7) as resp:
                headers = dict(resp.headers)
                content_length = int(headers.get("Content-Length", 0))
                etag = headers.get("ETag", "").strip('"')
                last_modified = headers.get("Last-Modified", "")
                return {
                    "online": True,
                    "content_length": content_length,
                    "etag": etag,
                    "last_modified": last_modified,
                }
        except Exception as e:
            logging.warning(f"HopToDesk: Falha ao verificar cabeçalhos remotos: {e}")
            return {"online": False, "error": str(e)}

    @classmethod
    def ensure_local_binary(cls, force_check: bool = True) -> Dict[str, Any]:
        """
        Garante que a versão mais recente do HopToDesk.exe esteja presente na pasta bin do AppData.
        Verifica se já existe localmente e se está atualizada antes de efetuar novo download.
        """
        exe_path = cls.get_local_exe_path()
        meta_path = cls.get_meta_path()
        local_exists = exe_path.exists() and exe_path.stat().st_size > 0

        saved_meta = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    saved_meta = json.load(f)
            except Exception:
                saved_meta = {}

        remote_info = cls.check_remote_version_info() if force_check else {"online": False}

        if local_exists:
            local_size = exe_path.stat().st_size
            # Se conseguimos consultar o servidor remoto:
            if remote_info.get("online"):
                remote_size = remote_info.get("content_length", 0)
                remote_etag = remote_info.get("etag", "")
                saved_etag = saved_meta.get("etag", "")

                # Se tamanho bate e ETag bate (ou salvo bate), já está 100% atualizado
                if remote_size > 0 and local_size == remote_size and (not remote_etag or remote_etag == saved_etag):
                    logging.info("HopToDesk local já está na versão mais recente.")
                    return {
                        "status": "up_to_date",
                        "path": str(exe_path),
                        "size": local_size,
                        "etag": remote_etag
                    }

            # Se estiver sem internet ou falhar o check remoto, mas o binário local existir
            elif not remote_info.get("online"):
                logging.info("HopToDesk: Servidor remoto inacessível, utilizando binário local em cache.")
                return {
                    "status": "cached",
                    "path": str(exe_path),
                    "size": local_size
                }

        # Se chegamos aqui, é necessário baixar ou atualizar o executável
        logging.info(f"Baixando última versão do HopToDesk de {cls.OFFICIAL_DOWNLOAD_URL}...")
        temp_download_path = cls.get_bin_dir() / "HopToDesk.exe.tmp"

        try:
            req = urllib.request.Request(
                cls.OFFICIAL_DOWNLOAD_URL,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=30) as response, open(temp_download_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)

            downloaded_size = temp_download_path.stat().st_size
            if downloaded_size < 1_000_000:
                raise ValueError(f"Download incompleto do HopToDesk (apenas {downloaded_size} bytes)")

            # Substituição atômica segura
            if exe_path.exists():
                try:
                    exe_path.unlink()
                except Exception:
                    pass
            temp_download_path.replace(exe_path)

            # Salvar metadados atualizados
            meta_data = {
                "etag": remote_info.get("etag", ""),
                "content_length": downloaded_size,
                "last_modified": remote_info.get("last_modified", ""),
                "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)

            logging.info(f"HopToDesk atualizado com sucesso ({downloaded_size} bytes).")
            return {
                "status": "downloaded",
                "path": str(exe_path),
                "size": downloaded_size,
                "etag": meta_data["etag"]
            }

        except Exception as e:
            if temp_download_path.exists():
                try:
                    temp_download_path.unlink()
                except Exception:
                    pass
            if local_exists:
                logging.warning(f"HopToDesk: Falha no download ({e}), mantendo versão existente.")
                return {"status": "cached", "path": str(exe_path), "size": exe_path.stat().st_size}
            raise RuntimeError(f"Falha ao baixar o HopToDesk: {e}")

        except Exception as e:
            logging.debug(f"Erro em _connect_smb_share: {e}")
            return False

    @classmethod
    def _connect_smb_share(cls, target_ip: str, username: str, password: str) -> bool:
        """
        Conecta ao compartilhamento administrativo C$ do host remoto via WNetAddConnection2W (em memória).
        Não cria processos, não usa cmd/powershell e não vaza credenciais em logs ou argumentos.
        """
        if sys.platform != "win32":
            return False

        try:
            mpr = ctypes.WinDLL("mpr.dll")
            WNetAddConnection2W = mpr.WNetAddConnection2W
            WNetAddConnection2W.argtypes = [
                ctypes.POINTER(_NETRESOURCEW),
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                wintypes.DWORD
            ]
            WNetAddConnection2W.restype = wintypes.DWORD

            remote_name = rf"\\{target_ip}\C$"
            nr = _NETRESOURCEW()
            nr.dwType = 1  # RESOURCETYPE_DISK
            nr.lpRemoteName = remote_name
            nr.lpLocalName = None
            nr.lpProvider = None

            # Conexão temporária (flags=0)
            res = WNetAddConnection2W(ctypes.byref(nr), password, username, 0)
            # 0 = NO_ERROR, 1219 = ERROR_SESSION_CREDENTIAL_CONFLICT (já conectado)
            if res in (0, 1219):
                return True
            logging.debug(f"WNetAddConnection2W retornou código: {res}")
            return False
        except Exception as e:
            logging.debug(f"Erro em _connect_smb_share: {e}")
            return False

    @classmethod
    def _disconnect_smb_share(cls, target_ip: str):
        """Desconecta o compartilhamento administrativo C$ após o término da cópia."""
        if sys.platform != "win32":
            return
        try:
            mpr = ctypes.WinDLL("mpr.dll")
            WNetCancelConnection2W = mpr.WNetCancelConnection2W
            WNetCancelConnection2W.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL]
            WNetCancelConnection2W.restype = wintypes.DWORD

            remote_name = rf"\\{target_ip}\C$"
            WNetCancelConnection2W(remote_name, 0, True)
        except Exception:
            pass

    @classmethod
    def deploy_and_get_id(
        cls,
        winrm_handler,
        target_ip: str,
        username: str,
        password: str,
        target_location: str = "public",
        target_user: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Fluxo completo:
        1. Garante que HopToDesk.exe está atualizado localmente no AppData.
        2. Determina o destino (Área de Trabalho Pública ou de um Usuário específico).
        3. Verifica se o HopToDesk já existe no host remoto.
        4. Caso não exista ou tamanho seja diferente, copia para o destino selecionado (via SMB ou WinRM).
        5. Executa 'HopToDesk.exe --get-id' via WinRM para obter o ID.
        6. Inicia o aplicativo na sessão do usuário no host remoto para que a janela abra para ele.
        7. Retorna o ID capturado.
        """
        yield {"status": "info", "message": "Verificando se o HopToDesk já está presente no host de destino..."}

        # Sanitizar target_user se fornecido
        clean_target_user = ""
        if target_user:
            raw_u = target_user.split("\\")[-1].split("/")[-1].strip()
            clean_target_user = "".join(c for c in raw_u if c.isalnum() or c in "._-")

        if target_location == "user" and clean_target_user:
            dest_remote_path = rf"C:\Users\{clean_target_user}\Desktop\HopToDesk.exe"
            dest_temp_path = rf"C:\Users\{clean_target_user}\Desktop\HopToDesk.exe.tmp"
            smb_dest_path = rf"\\{target_ip}\C$\Users\{clean_target_user}\Desktop\HopToDesk.exe"
            smb_dest_temp = rf"\\{target_ip}\C$\Users\{clean_target_user}\Desktop\HopToDesk.exe.tmp"
            location_desc = f"Área de Trabalho de {clean_target_user}"
        else:
            dest_remote_path = r"C:\Users\Public\Desktop\HopToDesk.exe"
            dest_temp_path = r"C:\Users\Public\Desktop\HopToDesk.exe.tmp"
            smb_dest_path = rf"\\{target_ip}\C$\Users\Public\Desktop\HopToDesk.exe"
            smb_dest_temp = rf"\\{target_ip}\C$\Users\Public\Desktop\HopToDesk.exe.tmp"
            location_desc = "Área de Trabalho Pública"

        # 1. Busca abrangente por HopToDesk existente no destino (processos, registro, desktops de usuarios)
        search_script = f'''
        $candidate = $null
        try {{
            $proc = Get-Process -Name "*hoptodesk*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path -First 1
            if ($proc -and (Test-Path $proc)) {{ $candidate = $proc }}
        }} catch {{}}

        if (-not $candidate) {{
            try {{
                $regCmd = (Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\\hoptodesk\\shell\\open\\command" -ErrorAction SilentlyContinue).'(default)'
                if ($regCmd -and $regCmd -match '([a-zA-Z]:\\\\[^"]+\\.exe)') {{
                    if (Test-Path $matches[1]) {{ $candidate = $matches[1] }}
                }}
            }} catch {{}}
        }}

        if (-not $candidate -and (Test-Path '{dest_remote_path}')) {{
            $candidate = '{dest_remote_path}'
        }}

        if (-not $candidate -and (Test-Path 'C:\\Users\\Public\\Desktop\\HopToDesk.exe')) {{
            $candidate = 'C:\\Users\\Public\\Desktop\\HopToDesk.exe'
        }}

        if (-not $candidate) {{
            foreach ($sp in @("$env:ProgramFiles\\HopToDesk\\HopToDesk.exe", "${{env:ProgramFiles(x86)}}\\HopToDesk\\HopToDesk.exe", "C:\\ProgramData\\HopToDesk\\HopToDesk.exe")) {{
                if ($sp -and (Test-Path $sp)) {{ $candidate = $sp; break }}
            }}
        }}

        if (-not $candidate) {{
            try {{
                $uDirs = Get-ChildItem "C:\\Users" -Directory -ErrorAction SilentlyContinue
                foreach ($u in $uDirs) {{
                    foreach ($sub in @("Desktop\\HopToDesk.exe", "Downloads\\HopToDesk.exe", "AppData\\Local\\HopToDesk\\HopToDesk.exe", "AppData\\Roaming\\HopToDesk\\HopToDesk.exe")) {{
                        $chk = Join-Path $u.FullName $sub
                        if (Test-Path $chk) {{ $candidate = $chk; break }}
                    }}
                    if ($candidate) {{ break }}
                }}
            }} catch {{}}
        }}

        if ($candidate) {{
            if (-not (Test-Path '{dest_remote_path}')) {{
                $destDir = Split-Path -Parent '{dest_remote_path}'
                if (-not (Test-Path $destDir)) {{ New-Item -ItemType Directory -Path $destDir -Force -ErrorAction SilentlyContinue | Out-Null }}
                Copy-Item -Path $candidate -Destination '{dest_remote_path}' -Force -ErrorAction SilentlyContinue
            }}
            $targetExe = if (Test-Path '{dest_remote_path}') {{ '{dest_remote_path}' }} else {{ $candidate }}
            $out = cmd.exe /c "`"$targetExe`" --get-id" 2>$null
            if (-not ($out -and $out -match '^\\s*(\\d{{7,12}})\\s*$')) {{
                $out = cmd.exe /c "`"$candidate`" --get-id" 2>$null
            }}
            $id = $null
            if ($out -and $out -match '^\\s*(\\d{{7,12}})\\s*$') {{
                $id = $matches[1]
            }}
            Write-Output "FOUND_CANDIDATE:$targetExe"
            if ($id) {{ Write-Output "CANDIDATE_ID:$id" }}
            exit
        }}
        Write-Output "NOT_FOUND"
        '''

        res_search = winrm_handler.execute_script(search_script)
        lines = [l.strip() for l in res_search.get("output", []) if l.strip()]
        found_existing = False
        existing_candidate = None
        existing_id = None
        for line in lines:
            if line.startswith("FOUND_CANDIDATE:"):
                found_existing = True
                existing_candidate = line.split(":", 1)[1].strip()
            elif line.startswith("CANDIDATE_ID:"):
                existing_id = line.split(":", 1)[1].strip()

        needs_copy = not found_existing
        if found_existing:
            yield {"status": "info", "message": f"HopToDesk já presente no host ({location_desc}). Garantindo execução..."}

        # 2. Se não encontrou nenhuma instalação existente, prepara o binário local para implantar
        if needs_copy:
            yield {"status": "info", "message": "Preparando binário atualizado do HopToDesk para implantação..."}
            try:
                local_res = cls.ensure_local_binary()
                local_path = local_res["path"]
                local_size = local_res["size"]
            except Exception as e:
                yield {"status": "error", "message": f"Erro ao preparar HopToDesk local: {e}"}
                return

            yield {"status": "info", "message": f"Copiando HopToDesk para {location_desc} do host..."}
            copied = False
            # Tentativa 1: SMB Administrativo (rápido e direto via Windows API)
            try:
                if cls._connect_smb_share(target_ip, username, password):
                    dest_dir = os.path.dirname(smb_dest_path)
                    if not os.path.exists(dest_dir):
                        try:
                            os.makedirs(dest_dir, exist_ok=True)
                        except Exception:
                            pass
                    shutil.copy2(local_path, smb_dest_temp)
                    if os.path.exists(smb_dest_path):
                        try:
                            os.remove(smb_dest_path)
                        except Exception:
                            pass
                    os.replace(smb_dest_temp, smb_dest_path)
                    copied = True
                    yield {"status": "info", "message": f"Cópia concluída com sucesso via compartilhamento administrativo para {location_desc}."}
            except Exception as e:
                logging.debug(f"SMB copy failed: {e}")
            finally:
                cls._disconnect_smb_share(target_ip)

            # Tentativa 2: Fallback via WinRM (chunked transfer)
            if not copied:
                yield {"status": "info", "message": f"Transferindo para {location_desc} via canal WinRM seguro (pode levar alguns instantes)..."}
                try:
                    import base64
                    # Criar diretório de destino se não existir e limpar temporário
                    dir_prep_script = (
                        f"$destDir = Split-Path -Parent '{dest_remote_path}'; "
                        f"if (-not (Test-Path $destDir)) {{ New-Item -ItemType Directory -Path $destDir -Force | Out-Null }}; "
                        f"Remove-Item '{dest_temp_path}' -Force -ErrorAction SilentlyContinue"
                    )
                    winrm_handler.execute_script(dir_prep_script)

                    chunk_size = 200 * 1024  # 200 KB por chunk
                    with open(local_path, "rb") as f:
                        part = 0
                        while True:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            b64 = base64.b64encode(chunk).decode("ascii")
                            append_script = (
                                f"$bytes = [Convert]::FromBase64String('{b64}'); "
                                f"[System.IO.File]::AppendAllBytes('{dest_temp_path}', $bytes)"
                            )
                            part_res = winrm_handler.execute_script(append_script)
                            if not part_res.get("success"):
                                raise RuntimeError(f"Falha na transferência do bloco {part}")
                            part += 1

                    # Mover temporário para o destino final
                    finalize_script = (
                        f"Move-Item -Path '{dest_temp_path}' "
                        f"-Destination '{dest_remote_path}' -Force; "
                        f"(Get-Item '{dest_remote_path}').Length"
                    )
                    fin_res = winrm_handler.execute_script(finalize_script)
                    fin_size = "".join(fin_res.get("output", [])).strip()
                    if fin_size.isdigit() and int(fin_size) == local_size:
                        copied = True
                        yield {"status": "info", "message": "Cópia concluída com sucesso via WinRM."}
                    else:
                        raise RuntimeError(f"Tamanho divergente após transferência: {fin_size}")
                except Exception as e:
                    yield {"status": "error", "message": f"Falha na cópia do HopToDesk para o destino: {e}"}
                    return

        # 4. Executar e obter o ID do HopToDesk
        yield {"status": "info", "message": "Iniciando HopToDesk na área de trabalho do usuário no host remoto..."}

        exec_script = f"""
        $exe = '{dest_remote_path}'
        if (-not (Test-Path $exe) -and (Test-Path 'C:\\Users\\Public\\Desktop\\HopToDesk.exe')) {{
            $exe = 'C:\\Users\\Public\\Desktop\\HopToDesk.exe'
        }}
        $targetUser = '{clean_target_user}'
        if (-not (Test-Path $exe)) {{
            Write-Output "EXE_NOT_FOUND"
            exit
        }}

        # 1. Obter ID do HopToDesk via cmd.exe /c para capturar stdout de binario GUI
        $htdId = '{existing_id or ""}'
        if (-not $htdId) {{
            try {{
                $rawId = cmd.exe /c "`"$exe`" --get-id" 2>$null
                if ($rawId -match '^\\s*(\\d{{7,12}})\\s*$') {{
                    $htdId = $matches[1]
                }}
            }} catch {{}}
        }}

        # 2. Verificar se HopToDesk ja esta rodando como processo
        $procAlreadyRunning = [bool](Get-Process -Name "*hoptodesk*" -ErrorAction SilentlyContinue)

        # 3. Se nao estiver em execucao, abrir diretamente no desktop interativo do usuario logado
        if (-not $procAlreadyRunning) {{
            $usersToLaunch = [System.Collections.Generic.List[string]]::new()

            # Metodo A: Usuario do console/desktop ativo
            try {{
                $cs = (Get-CimInstance Win32_ComputerSystem).UserName
                if ($cs -and (-not $usersToLaunch.Contains($cs))) {{ $usersToLaunch.Add($cs) }}
            }} catch {{}}

            # Metodo B: Donos de processos explorer.exe ativos (sessoes graficas abertas)
            try {{
                $explorers = Get-CimInstance Win32_Process -Filter "Name = 'explorer.exe'" -ErrorAction SilentlyContinue
                foreach ($exp in $explorers) {{
                    $o = Invoke-CimMethod -InputObject $exp -MethodName GetOwner -ErrorAction SilentlyContinue
                    if ($o -and $o.Domain -and $o.User) {{
                        $fullU = "$($o.Domain)\\$($o.User)"
                        if (-not $usersToLaunch.Contains($fullU)) {{ $usersToLaunch.Add($fullU) }}
                    }}
                }}
            }} catch {{}}

            # Metodo C: Se targetUser foi informado, adicionar variacoes
            if ($targetUser) {{
                $compU = "$env:COMPUTERNAME\\$targetUser"
                if (-not $usersToLaunch.Contains($compU)) {{ $usersToLaunch.Add($compU) }}
                if (-not $usersToLaunch.Contains($targetUser)) {{ $usersToLaunch.Add($targetUser) }}
            }}

            # Iniciar diretamente no desktop interativo do usuario via schtasks.exe (imune a restrições DCOM do WinRM)
            $taskName = "HopToDesk_Run_" + (Get-Random)
            $taskCreated = $false
            $trArg = '\"' + $exe + '\"'

            foreach ($uName in $usersToLaunch) {{
                if (-not $uName) {{ continue }}
                $createCmd = "schtasks /create /tn `"$taskName`" /tr $trArg /sc ONCE /st 23:59 /it /ru `"$uName`" /rl HIGHEST /f"
                $null = cmd.exe /c $createCmd 2>&1
                if ($LASTEXITCODE -eq 0) {{
                    $taskCreated = $true
                    break
                }}
            }}

            if (-not $taskCreated) {{
                $createCmd = "schtasks /create /tn `"$taskName`" /tr $trArg /sc ONCE /st 23:59 /it /rl HIGHEST /f"
                $null = cmd.exe /c $createCmd 2>&1
                if ($LASTEXITCODE -eq 0) {{
                    $taskCreated = $true
                }}
            }}

            if ($taskCreated) {{
                $null = cmd.exe /c "schtasks /run /tn `"$taskName`"" 2>&1
                Start-Sleep -Seconds 2
                $null = cmd.exe /c "schtasks /delete /tn `"$taskName`" /f" 2>&1
            }} else {{
                Start-Process -FilePath $exe -WindowStyle Normal -ErrorAction SilentlyContinue
            }}
        }}

        if ($htdId) {{
            Write-Output "HOPTODESK_ID:$htdId"
        }} else {{
            Start-Sleep -Seconds 1
            try {{
                $rawId2 = cmd.exe /c "`"$exe`" --get-id" 2>$null
                if ($rawId2 -match '^\\s*(\\d{{7,12}})\\s*$') {{
                    Write-Output "HOPTODESK_ID:$($matches[1])"
                }} else {{
                    Write-Output "ID_NOT_RESOLVED"
                }}
            }} catch {{
                Write-Output "ID_NOT_RESOLVED"
            }}
        }}

        # 4. Verificar se processo esta ativo no host (aguarda ate 5 segundos)
        $isProcActive = $false
        for ($chk = 0; $chk -lt 5; $chk++) {{
            $pCheck = Get-Process -Name "*hoptodesk*" -ErrorAction SilentlyContinue
            if ($pCheck) {{ $isProcActive = $true; break }}
            Start-Sleep -Seconds 1
        }}
        Write-Output "HOPTODESK_RUNNING:$isProcActive"
        """

        exec_res = winrm_handler.execute_script(exec_script)
        output_lines = [line.strip() for line in exec_res.get("output", []) if line.strip()]

        found_id = None
        is_running = True
        for line in output_lines:
            if line.startswith("HOPTODESK_ID:"):
                found_id = line.split(":", 1)[1].strip()
            elif line.startswith("HOPTODESK_RUNNING:"):
                is_running = "true" in line.lower()

        if found_id:
            if is_running:
                yield {"status": "success", "message": f"HopToDesk implantado e em execução! ID: {found_id}", "data": found_id, "running": True}
            else:
                yield {"status": "warning", "message": f"HopToDesk copiado (ID: {found_id}), mas a inicialização na tela do usuário não foi confirmada.", "data": found_id, "running": False}
        else:
            yield {"status": "error", "message": "Não foi possível implantar ou identificar o HopToDesk no host remoto."}

    @classmethod
    def launch_local(cls, target_id: Optional[str] = None) -> bool:
        """
        Abre o HopToDesk no computador do operador conectando diretamente ao ID remoto.
        Garante que a janela do aplicativo abra normalmente para interação do usuário.
        """
        clean_id = "".join(filter(str.isdigit, str(target_id or "")))

        # Locais possíveis do executável local
        candidates = [
            cls.get_local_exe_path(),
            Path(os.path.expanduser("~/Desktop")) / "HopToDesk.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "HopToDesk" / "HopToDesk.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "HopToDesk" / "HopToDesk.exe",
            Path(r"C:\Users\Public\Desktop\HopToDesk.exe"),
        ]

        exe_to_run = None
        for p in candidates:
            if p.exists() and p.stat().st_size > 0:
                exe_to_run = str(p)
                break

        # Se não encontramos nenhum local, tenta garantir o download no AppData
        if not exe_to_run:
            try:
                res = cls.ensure_local_binary()
                if os.path.exists(res.get("path", "")):
                    exe_to_run = res["path"]
            except Exception as e:
                logging.error(f"HopToDesk: Falha ao garantir binário local para execução: {e}")

        # Se ainda assim não encontrar, tentar via protocolo URL registrado
        if not exe_to_run and clean_id:
            try:
                import webbrowser
                webbrowser.open(f"hoptodesk://{clean_id}")
                return True
            except Exception:
                return False

        if not exe_to_run:
            return False

        try:
            args = [exe_to_run]
            if clean_id:
                args.extend(["--connect", clean_id])
            # Executar de forma independente para que a interface gráfica abra em primeiro plano para o operador
            subprocess.Popen(args)
            return True
        except Exception as e:
            logging.error(f"Erro ao iniciar HopToDesk localmente: {e}")
            return False
