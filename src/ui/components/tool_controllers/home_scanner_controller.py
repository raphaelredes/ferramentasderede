# app/ui_components/tool_controllers/home_scanner_controller.py
from .base_controller import BaseToolController

class HomeScannerController(BaseToolController):
    def __init__(self, app):
        # Inicializa com um host placeholder, pois não está atrelado a uma aba específica
        super().__init__(app, host={}, hostname="")

    def get_credentials_for_remote_scan(self, target_host):
        """
        Um método wrapper para usar o _get_credentials_with_vault 
        para um host específico selecionado no scanner.
        """
        # Define temporariamente o host e hostname para o diálogo de credenciais
        self.host = target_host
        self.hostname = target_host.get("name", "")
        
        username, password = self._get_credentials_with_vault()
        
        # Reseta para o placeholder
        self.host = {}
        self.hostname = ""
        
        return username, password