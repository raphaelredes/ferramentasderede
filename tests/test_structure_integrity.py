#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes de Integridade da Nova Estrutura

Verifica se todos os módulos podem ser importados corretamente
e se a estrutura do projeto está consistente.
"""

import sys
import os
import unittest
from pathlib import Path

# Adicionar o diretório src ao path
project_root = Path(__file__).parent.parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))


class TestStructureIntegrity(unittest.TestCase):
    """Testa a integridade da nova estrutura do projeto."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        self.project_root = project_root
        self.src_dir = src_dir
        
    def test_main_package_import(self):
        """Testa se o pacote principal pode ser importado."""
        try:
            import core
            self.assertTrue(True, "Pacote principal importado com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar pacote principal: {e}")
    
    def test_core_modules_import(self):
        """Testa se os módulos do core podem ser importados."""
        core_modules = [
            'core.app',
            'core.controller',
            'core.host_manager',
            'core.settings_manager'
        ]
        
        for module in core_modules:
            with self.subTest(module=module):
                try:
                    __import__(module)
                    self.assertTrue(True, f"Módulo {module} importado com sucesso")
                except ImportError as e:
                    self.fail(f"Falha ao importar {module}: {e}")
    
    def test_network_modules_import(self):
        """Testa se os módulos de rede podem ser importados."""
        network_modules = [
            'network.tools',
            'network.discovery',
            'network.optimizer'
        ]
        
        for module in network_modules:
            with self.subTest(module=module):
                try:
                    __import__(module)
                    self.assertTrue(True, f"Módulo {module} importado com sucesso")
                except ImportError as e:
                    self.fail(f"Falha ao importar {module}: {e}")
    
    def test_system_modules_import(self):
        """Testa se os módulos do sistema podem ser importados."""
        system_modules = [
            'system.tools',
            'system.optimizer',
            'system.advanced_optimizer'
        ]
        
        for module in system_modules:
            with self.subTest(module=module):
                try:
                    __import__(module)
                    self.assertTrue(True, f"Módulo {module} importado com sucesso")
                except ImportError as e:
                    self.fail(f"Falha ao importar {module}: {e}")
    
    def test_ui_components_import(self):
        """Testa se os principais componentes de UI podem ser importados."""
        ui_modules = [
            'ui.components.app_ui_manager',
            'ui.components.host_tab_view',
            'ui.components.custom_dialogs',
            'ui.components.credential_service'
        ]
        
        for module in ui_modules:
            with self.subTest(module=module):
                try:
                    __import__(module)
                    self.assertTrue(True, f"Módulo {module} importado com sucesso")
                except ImportError as e:
                    self.fail(f"Falha ao importar {module}: {e}")
    
    def test_config_import(self):
        """Testa se o módulo de configuração pode ser importado."""
        try:
            from config.settings import (
                APP_VERSION, MONOSPACE_FONT, DISCOVERY_CACHE_FILE,
                STATUS_PING_TIMEOUT, UI_PREFS_FILE
            )
            self.assertTrue(True, "Configurações importadas com sucesso")
        except ImportError as e:
            self.fail(f"Falha ao importar configurações: {e}")
    
    def test_utils_import(self):
        """Testa se os utilitários podem ser importados."""
        utils_modules = [
            'utils.translation',
            'utils.theme'
        ]
        
        for module in utils_modules:
            with self.subTest(module=module):
                try:
                    __import__(module)
                    self.assertTrue(True, f"Módulo {module} importado com sucesso")
                except ImportError as e:
                    self.fail(f"Falha ao importar {module}: {e}")
    
    def test_directory_structure(self):
        """Testa se a estrutura de diretórios está correta."""
        expected_dirs = [
            'src',
            'src/core',
            'src/network',
            'src/system',
            'src/ui',
            'src/ui/components',
            'src/config',
            'src/utils',
            'tests',
            'docs',
            'data',
            'assets'
        ]
        
        for dir_path in expected_dirs:
            full_path = self.project_root / dir_path
            with self.subTest(directory=dir_path):
                self.assertTrue(
                    full_path.exists() and full_path.is_dir(),
                    f"Diretório {dir_path} deve existir"
                )
    
    def test_init_files_exist(self):
        """Testa se os arquivos __init__.py existem onde necessário."""
        init_files = [
            'src/__init__.py',
            'src/core/__init__.py',
            'src/network/__init__.py',
            'src/system/__init__.py',
            'src/ui/__init__.py',
            'src/ui/components/__init__.py',
            'src/config/__init__.py',
            'src/utils/__init__.py'
        ]
        
        for init_file in init_files:
            full_path = self.project_root / init_file
            with self.subTest(init_file=init_file):
                self.assertTrue(
                    full_path.exists() and full_path.is_file(),
                    f"Arquivo __init__.py deve existir em {init_file}"
                )
    
    def test_main_entry_points(self):
        """Testa se os pontos de entrada principais existem."""
        entry_points = [
            'main_new.py',
            'setup.py',
            'requirements.txt',
            'README.md',
            '.gitignore'
        ]
        
        for entry_point in entry_points:
            full_path = self.project_root / entry_point
            with self.subTest(entry_point=entry_point):
                self.assertTrue(
                    full_path.exists() and full_path.is_file(),
                    f"Arquivo {entry_point} deve existir na raiz do projeto"
                )


class TestModuleFunctionality(unittest.TestCase):
    """Testa a funcionalidade básica dos módulos."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        # Configurar diretório base para testes
        self.base_dir = str(project_root)
    
    def test_network_tools_instantiation(self):
        """Testa se NetworkTools pode ser instanciado."""
        try:
            from network.tools import NetworkTools
            tools = NetworkTools()
            self.assertIsInstance(tools, NetworkTools)
        except Exception as e:
            self.fail(f"Falha ao instanciar NetworkTools: {e}")
    
    def test_host_manager_instantiation(self):
        """Testa se HostManager pode ser instanciado."""
        try:
            from core.host_manager import HostManager
            manager = HostManager()
            self.assertIsInstance(manager, HostManager)
        except Exception as e:
            self.fail(f"Falha ao instanciar HostManager: {e}")
    
    def test_config_values(self):
        """Testa se as configurações têm valores válidos."""
        try:
            from config.settings import (
                APP_VERSION, STATUS_PING_TIMEOUT, MONOSPACE_FONT
            )
            
            self.assertIsInstance(APP_VERSION, str)
            self.assertGreater(len(APP_VERSION), 0)
            
            self.assertIsInstance(STATUS_PING_TIMEOUT, (int, float))
            self.assertGreater(STATUS_PING_TIMEOUT, 0)
            
            self.assertIsInstance(MONOSPACE_FONT, (tuple, list))
            self.assertEqual(len(MONOSPACE_FONT), 2)
            
        except Exception as e:
            self.fail(f"Falha ao verificar configurações: {e}")


if __name__ == '__main__':
    # Executar testes
    unittest.main(verbosity=2)
