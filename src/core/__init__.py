"""
Módulo Core - Funcionalidades Principais da Aplicação

Contém as classes e funcionalidades fundamentais da aplicação:
- AppController: Controlador principal da aplicação
- NetworkToolsApp: Classe principal da aplicação GUI
- HostManager: Gerenciamento de hosts
- AppSettingsManager: Gerenciamento de configurações
"""

from .app import App as NetworkToolsApp
from .controller import AppController
from .host_manager import HostManager
from .settings_manager import AppSettingsManager

__all__ = [
    "NetworkToolsApp",
    "AppController", 
    "HostManager",
    "AppSettingsManager"
]
