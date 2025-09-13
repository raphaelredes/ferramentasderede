# app/discovery_scanner.py
# Contém a lógica de negócios para a varredura de rede, separada da UI.

import threading
import ipaddress
import logging
from .tools import NetworkTools
from src.system.tools import SystemTools
# A importação de 'get_credentials' foi REMOVIDA.

class DiscoveryScanner:
    def __init__(self, app, callbacks):
        self.app = app
        self.network_tools = NetworkTools()
        # CORREÇÃO AQUI: Passe o 'app' para o SystemTools
        self.system_tools = SystemTools(self.app)
        
        self.on_status_update = callbacks.get('on_status_update')
        self.on_host_found = callbacks.get('on_host_found')
        self.on_scan_finished = callbacks.get('on_scan_finished')

        self.scan_thread = None
        self.stop_scan_event = threading.Event()

    def start_scan(self, scan_type, scan_target=None, remote_host_info=None):
        """Inicia uma varredura de rede em uma thread separada."""
        if self.is_running():
            logging.warning("Scan already in progress. Not starting a new one.")
            return

        self.stop_scan_event.clear()
        self.scan_thread = threading.Thread(
            name="DiscoveryScanWorker",
            target=self._scan_worker,
            args=(scan_type, scan_target, remote_host_info),
            daemon=True
        )
        self.scan_thread.start()

    def stop_scan(self):
        """Sinaliza para a thread de varredura parar."""
        if self.is_running():
            self.stop_scan_event.set()
            logging.info("Scan stop requested.")
            self._update_status("Parando varredura...")

    def is_running(self):
        """Verifica se uma varredura está em andamento."""
        return self.scan_thread and self.scan_thread.is_alive()

    def _scan_worker(self, scan_type, scan_target, remote_host_info):
        """O método principal que executa a lógica de varredura na thread."""
        try:
            logging.debug(f"Scan worker started with type: {scan_type}")
            if scan_type == "local":
                self._local_scan_logic()
            elif scan_type == "remote":
                # Log remote host info without sensitive password
                self._remote_scan_logic({k: v for k, v in remote_host_info.items() if k != 'password'})
            elif scan_type == "custom" and scan_target:
                self._custom_scan_logic(scan_target)
        except Exception as e:
            self._update_status(f"Ocorreu um erro fatal: {e}")
        finally:
            if self.on_scan_finished:
                self.app.after(0, self.on_scan_finished)

    def _local_scan_logic(self):
        network_info = self.network_tools.get_local_network_info()
        if "error" in network_info:
            self._update_status(f"Erro: {network_info.get('error')}")
            return
        network = network_info['network']
        self._update_status(f"Varrendo rede: {network} ({network.num_addresses} hosts)")
        self._run_scan_loop(self.network_tools.discover_hosts(network))

    def _remote_scan_logic(self, remote_host_info):
        if not remote_host_info or "username" not in remote_host_info:
            # Se as credenciais não foram fornecidas (usuário cancelou), para aqui.
            self._update_status(self.app.translate("user_cancelled_operation"))
            return
        
        username = remote_host_info.get("username")
        password = remote_host_info.get("password")
            
        self._update_status(self.app.translate("scanner_remote_connecting", host=remote_host_info['name']))
        
        generator = self.system_tools.execute_remote_network_scan(
            remote_host_info['ip'], username, password
        )
        self._run_scan_loop(generator)

    def _custom_scan_logic(self, network):
        self._update_status(f"Varrendo rede personalizada: {network} ({network.num_addresses} hosts)")
        self._run_scan_loop(self.network_tools.discover_hosts(network))

    def _run_scan_loop(self, generator):
        count = 0
        for result in generator:
            if self.stop_scan_event.is_set():
                break
            
            if result.get("status") == "progress":
                self._update_status(result["message"])
            elif result.get("status") == "error":
                self._update_status(f"Erro Remoto: {result['message']}")
            elif "ip" in result and self.on_host_found:
                count += 1
                self.app.after(0, self.on_host_found, result)
        
        final_msg = f"Concluído. {count} dispositivo(s) encontrado(s)." if not self.stop_scan_event.is_set() else "Interrompido pelo usuário."
        self._update_status(final_msg)

    def _update_status(self, text):
        if self.on_status_update:
            self.app.after(0, self.on_status_update, text)