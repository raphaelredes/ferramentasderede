#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes de Integração da UI

Testa a integração dos componentes de interface da nova estrutura,
incluindo diálogos, gerenciadores e widgets principais.
"""

import sys
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Adicionar o diretório src ao path
project_root = Path(__file__).parent.parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))


class TestUIManagerIntegration(unittest.TestCase):
    """Testa a integração do AppUIManager."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        # Criar mock da aplicação principal
        self.mock_app = Mock()
        self.mock_app.base_dir = str(project_root)
        self.mock_app.translate = lambda x, **kwargs: x.format(**kwargs) if kwargs else x
        self.mock_app.show_info = Mock()
        self.mock_app.show_error = Mock()
        self.mock_app.app_ctk_icon = None
        
        # Mock do translator
        self.mock_translator = Mock()
        self.mock_translator.translate = lambda x, **kwargs: x.format(**kwargs) if kwargs else x
    
    def test_app_ui_manager_import(self):
        """Testa se AppUIManager pode ser importado."""
        try:
            from ferramentasderede.ui.components.app_ui_manager import AppUIManager
            self.assertTrue(True, "AppUIManager importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar AppUIManager: {e}")
    
    @patch('ferramentasderede.ui.components.app_ui_manager.customtkinter')
    def test_app_ui_manager_instantiation(self, mock_ctk):
        """Testa se AppUIManager pode ser instanciado."""
        try:
            from ferramentasderede.ui.components.app_ui_manager import AppUIManager
            
            # Configurar mocks básicos
            mock_ctk.CTkFrame.return_value = Mock()
            mock_ctk.CTkLabel.return_value = Mock()
            mock_ctk.CTkButton.return_value = Mock()
            
            ui_manager = AppUIManager(self.mock_app, self.mock_translator)
            self.assertIsInstance(ui_manager, AppUIManager)
            
        except Exception as e:
            self.fail(f"Falha ao instanciar AppUIManager: {e}")


class TestDialogComponents(unittest.TestCase):
    """Testa os componentes de diálogo da nova estrutura."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        # Criar mock da aplicação
        self.mock_app = Mock()
        self.mock_app.translate = lambda x, **kwargs: x.format(**kwargs) if kwargs else x
        self.mock_app.show_info = Mock()
        self.mock_app.show_error = Mock()
        self.mock_app.base_dir = str(project_root)
    
    def test_custom_dialogs_import(self):
        """Testa se CustomDialogs podem ser importados."""
        try:
            from ferramentasderede.ui.components.custom_dialogs import (
                CustomMessageBox, PasswordInputDialog
            )
            self.assertTrue(True, "CustomDialogs importados com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar CustomDialogs: {e}")
    
    def test_credential_dialog_import(self):
        """Testa se CredentialDialog pode ser importado."""
        try:
            from ferramentasderede.ui.components.credential_dialog import CredentialDialog
            self.assertTrue(True, "CredentialDialog importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar CredentialDialog: {e}")
    
    def test_add_host_dialog_import(self):
        """Testa se AddHostDialog pode ser importado."""
        try:
            from ferramentasderede.ui.components.add_host_dialog import AddHostDialog
            self.assertTrue(True, "AddHostDialog importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar AddHostDialog: {e}")


class TestHostTabIntegration(unittest.TestCase):
    """Testa a integração dos componentes de abas de host."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        self.mock_app = Mock()
        self.mock_app.translate = lambda x, **kwargs: x.format(**kwargs) if kwargs else x
        self.mock_app.show_info = Mock()
        self.mock_app.show_error = Mock()
    
    def test_host_tab_view_import(self):
        """Testa se HostTabView pode ser importado."""
        try:
            from ferramentasderede.ui.components.host_tab_view import HostTabView
            self.assertTrue(True, "HostTabView importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar HostTabView: {e}")
    
    def test_tab_manager_import(self):
        """Testa se HostTabManager pode ser importado."""
        try:
            from ferramentasderede.ui.components.host_tab_manager.tab_manager import HostTabManager
            self.assertTrue(True, "HostTabManager importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar HostTabManager: {e}")
    
    def test_tool_factory_import(self):
        """Testa se ToolFrameFactory pode ser importado."""
        try:
            from ferramentasderede.ui.components.host_tab_manager.tool_factory import ToolFrameFactory
            self.assertTrue(True, "ToolFrameFactory importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar ToolFrameFactory: {e}")


class TestToolControllers(unittest.TestCase):
    """Testa os controladores de ferramentas da nova estrutura."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        self.mock_app = Mock()
        self.mock_app.translate = lambda x, **kwargs: x.format(**kwargs) if kwargs else x
        self.mock_app.show_info = Mock()
        self.mock_app.show_error = Mock()
        
        self.mock_host = {'ip': '192.168.1.100', 'name': 'test-host'}
        self.mock_hostname = 'test-host'
    
    def test_base_controller_import(self):
        """Testa se BaseToolController pode ser importado."""
        try:
            from ferramentasderede.ui.components.tool_controllers.base_controller import BaseToolController
            self.assertTrue(True, "BaseToolController importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar BaseToolController: {e}")
    
    def test_network_tool_controller_import(self):
        """Testa se NetworkToolController pode ser importado."""
        try:
            from ferramentasderede.ui.components.tool_controllers.network_tool_controller import NetworkToolController
            self.assertTrue(True, "NetworkToolController importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar NetworkToolController: {e}")
    
    @patch('ferramentasderede.ui.components.tool_controllers.base_controller.NetworkTools')
    @patch('ferramentasderede.ui.components.tool_controllers.base_controller.SystemTools')
    def test_base_controller_instantiation(self, mock_system_tools, mock_network_tools):
        """Testa se BaseToolController pode ser instanciado."""
        try:
            from ferramentasderede.ui.components.tool_controllers.base_controller import BaseToolController
            
            controller = BaseToolController(self.mock_app, self.mock_host, self.mock_hostname)
            self.assertIsInstance(controller, BaseToolController)
            self.assertEqual(controller.app, self.mock_app)
            self.assertEqual(controller.host, self.mock_host)
            self.assertEqual(controller.hostname, self.mock_hostname)
            
        except Exception as e:
            self.fail(f"Falha ao instanciar BaseToolController: {e}")


class TestCredentialService(unittest.TestCase):
    """Testa o serviço de credenciais da nova estrutura."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        # Criar diretório temporário para testes
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Limpeza após os testes."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_credential_service_import(self):
        """Testa se CredentialService pode ser importado."""
        try:
            from ferramentasderede.ui.components.credential_service import CredentialService
            self.assertTrue(True, "CredentialService importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar CredentialService: {e}")
    
    def test_credential_service_instantiation(self):
        """Testa se CredentialService pode ser instanciado."""
        try:
            from ferramentasderede.ui.components.credential_service import CredentialService
            
            service = CredentialService(self.temp_dir)
            self.assertIsInstance(service, CredentialService)
            self.assertFalse(service.is_unlocked())
            
        except Exception as e:
            self.fail(f"Falha ao instanciar CredentialService: {e}")


class TestFrameComponents(unittest.TestCase):
    """Testa os componentes de frame da nova estrutura."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        self.mock_app = Mock()
        self.mock_app.translate = lambda x, **kwargs: x.format(**kwargs) if kwargs else x
    
    def test_ping_frame_import(self):
        """Testa se PingFrame pode ser importado."""
        try:
            from ferramentasderede.ui.components.ping_frame import PingFrame
            self.assertTrue(True, "PingFrame importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar PingFrame: {e}")
    
    def test_traceroute_frame_import(self):
        """Testa se TracerouteFrame pode ser importado."""
        try:
            from ferramentasderede.ui.components.traceroute_frame import TracerouteFrame
            self.assertTrue(True, "TracerouteFrame importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar TracerouteFrame: {e}")
    
    def test_system_tools_frame_import(self):
        """Testa se SystemToolsFrame pode ser importado."""
        try:
            from ferramentasderede.ui.components.system_tools_frame import SystemToolsFrame
            self.assertTrue(True, "SystemToolsFrame importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar SystemToolsFrame: {e}")


class TestUtilsIntegration(unittest.TestCase):
    """Testa a integração dos utilitários da nova estrutura."""
    
    def test_translation_manager_import(self):
        """Testa se TranslationManager pode ser importado."""
        try:
            from ferramentasderede.utils.translation import TranslationManager
            self.assertTrue(True, "TranslationManager importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar TranslationManager: {e}")
    
    def test_theme_enhancer_import(self):
        """Testa se ThemeEnhancer pode ser importado."""
        try:
            from ferramentasderede.utils.theme import ThemeEnhancer
            self.assertTrue(True, "ThemeEnhancer importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar ThemeEnhancer: {e}")
    
    def test_translation_manager_instantiation(self):
        """Testa se TranslationManager pode ser instanciado."""
        try:
            from ferramentasderede.utils.translation import TranslationManager
            
            # Usar diretório temporário para testes
            temp_dir = tempfile.mkdtemp()
            translator = TranslationManager(languages_dir=temp_dir)
            self.assertIsInstance(translator, TranslationManager)
            
            # Limpeza
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        except Exception as e:
            self.fail(f"Falha ao instanciar TranslationManager: {e}")


if __name__ == '__main__':
    # Executar testes
    unittest.main(verbosity=2)
