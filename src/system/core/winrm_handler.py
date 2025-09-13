# src/ferramentasderede/system/core/winrm_handler.py
# Lida com a conexão e execução de comandos via WinRM, com sessão e objeto PowerShell persistentes.

import time
import json
import base64
from pypsrp.wsman import WSMan
from pypsrp.powershell import PowerShell, RunspacePool
from pypsrp.exceptions import WinRMError
from requests.exceptions import ConnectionError, ConnectTimeout

class WinRMHandler:
    def __init__(self, target_ip, username, password):
        self.target_ip = target_ip
        self.username = username
        self.password = password
        self.wsman = None
        self.pool = None
        self.ps = None  # Objeto PowerShell persistente

    def connect(self):
        """Estabelece a conexão e abre um RunspacePool e PowerShell persistentes."""
        try:
            self.wsman = WSMan(
                server=self.target_ip, username=self.username, password=self.password,
                ssl=False, connection_timeout=20, auth_method='negotiate'
            )
            self.pool = RunspacePool(self.wsman, configuration_name='Microsoft.PowerShell')
            # Abre explicitamente o pool para negociar o protocolo e estar pronto para uso.
            # Isso evita erros onde 'add_script' é chamado antes de o protocolo ser negociado.
            self.pool.open()
            # Cria a instância do PowerShell uma única vez e a reutiliza
            self.ps = PowerShell(self.pool)
            return {"success": True}
        except (WinRMError, ConnectionError, ConnectTimeout) as e:
            return {"error": str(e), "exception_obj": e}
        except Exception as e:
            return {"error": f"Exceção na conexão WinRM: {e}", "exception_obj": e}

    def close(self):
        """Fecha o RunspacePool e a conexão WSMan."""
        if self.pool:
            self.pool.close()
            self.pool = None
        if self.wsman:
            self.wsman.close()
            self.wsman = None
        self.ps = None

    def _clear_powershell_state(self):
        """Garante que a instância do PowerShell esteja limpa para um novo comando."""
        if self.ps:
            self.ps.commands.clear()
            # Limpa os streams individuais, pois ps.streams.clear() não existe
            # O stream 'output' é tratado de forma diferente no streaming e não precisa/deve ser limpo aqui.
            self.ps.streams.error.clear()
            self.ps.streams.verbose.clear()
            self.ps.streams.warning.clear()
            self.ps.streams.information.clear()
            self.ps.streams.debug.clear()


    def execute_script(self, script: str):
        """Executa um script simples e retorna a saída completa."""
        if not self.pool:
            return {"error": "Conexão não está ativa (pool não existe)."}
        
        # Cria uma nova instância de PowerShell para cada execução
        ps = PowerShell(self.pool)
        ps.add_script(script)
        output_list = ps.invoke()

        if ps.had_errors:
            error_msg = ""
            if ps.streams.error:
                error_msg = "\n".join([str(e) for e in ps.streams.error])
            else:
                error_msg = "Erro desconhecido no script PowerShell."
            
            # Escreve o erro no arquivo Errors.txt
            try:
                with open("Errors.txt", "a", encoding="utf-8") as f:
                    f.write(f"--- ERRO POWERSHELL ---\n{error_msg}\n-----------------------\n")
            except Exception as log_e:
                print(f"Falha ao escrever no Errors.txt: {log_e}")

            return {"error": f"Erro no Script Remoto: {error_msg}"}
        
        return {"success": True, "output": output_list}
        
        return {"success": True, "output": output_list}

    def execute_streaming_command(self, command: str):
        """Executa um comando e transmite a saída (stdout e stderr) em tempo real."""
        if not self.ps:
            yield "ERRO: Conexão não está ativa.\n"
            return

        self._clear_powershell_state()
        self.ps.add_script(f"$OutputEncoding = [System.Text.Encoding]::UTF8; {command}")
        
        self.ps.begin_invoke()

        while self.ps.invocation_state_info.state == 'Running':
            if self.ps.streams.output:
                for line in self.ps.streams.output:
                    yield str(line) + "\n"
                self.ps.streams.output.clear()
            
            if self.ps.streams.error:
                for error in self.ps.streams.error:
                    yield f"ERRO: {error}\n"
                self.ps.streams.error.clear()
            
            time.sleep(0.1)

        # Pega qualquer saída restante
        if self.ps.streams.output:
            for line in self.ps.streams.output:
                yield str(line) + "\n"
            self.ps.streams.output.clear()

        if self.ps.had_errors and self.ps.streams.error:
            for error in self.ps.streams.error:
                yield f"ERRO FINAL: {error}\n"
            self.ps.streams.error.clear()