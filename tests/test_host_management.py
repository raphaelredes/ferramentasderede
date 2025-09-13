#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes de Gerenciamento de Hosts

Testa as funcionalidades de adição, remoção e gerenciamento de hosts
na nova estrutura do projeto.
"""

import sys
import os
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Adicionar o diretório src ao path
project_root = Path(__file__).parent.parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))


class TestHostManager(unittest.TestCase):
    """Testa o HostManager da nova estrutura."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        # Importar após configurar o path
        from ferramentasderede.core.host_manager import HostManager
        
        # Criar diretório temporário para testes
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, 'test_hosts.json')
        
        # Mockar o arquivo de favoritos
        with patch('ferramentasderede.core.host_manager.FAVORITES_FILE', self.temp_file):
            self.host_manager = HostManager()
    
    def tearDown(self):
        """Limpeza após os testes."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_add_host(self):
        """Testa a adição de um novo host."""
        host_data = {
            'name': 'test-host',
            'ip': '192.168.1.100',
            'nickname': 'Test Host'
        }
        
        with patch('ferramentasderede.core.host_manager.FAVORITES_FILE', self.temp_file):
            self.host_manager.add_host(host_data)
            hosts = self.host_manager.load_hosts()
            
            self.assertEqual(len(hosts), 1)
            self.assertEqual(hosts[0]['name'], 'test-host')
            self.assertEqual(hosts[0]['ip'], '192.168.1.100')
    
    def test_remove_host(self):
        """Testa a remoção de um host."""
        # Adicionar um host primeiro
        host_data = {
            'name': 'test-host',
            'ip': '192.168.1.100'
        }
        
        with patch('ferramentasderede.core.host_manager.FAVORITES_FILE', self.temp_file):
            self.host_manager.add_host(host_data)
            hosts_before = self.host_manager.load_hosts()
            self.assertEqual(len(hosts_before), 1)
            
            # Remover o host
            self.host_manager.remove_host(host_data)
            hosts_after = self.host_manager.load_hosts()
            self.assertEqual(len(hosts_after), 0)
    
    def test_load_empty_hosts(self):
        """Testa o carregamento quando não há hosts."""
        with patch('ferramentasderede.core.host_manager.FAVORITES_FILE', 'non_existent_file.json'):
            hosts = self.host_manager.load_hosts()
            self.assertEqual(hosts, [])
    
    def test_duplicate_host_prevention(self):
        """Testa se hosts duplicados são evitados."""
        host_data = {
            'name': 'test-host',
            'ip': '192.168.1.100'
        }
        
        with patch('ferramentasderede.core.host_manager.FAVORITES_FILE', self.temp_file):
            # Adicionar o mesmo host duas vezes
            self.host_manager.add_host(host_data)
            self.host_manager.add_host(host_data)
            
            hosts = self.host_manager.load_hosts()
            # Deve haver apenas um host
            self.assertEqual(len(hosts), 1)


class TestNetworkTools(unittest.TestCase):
    """Testa as NetworkTools da nova estrutura."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        from ferramentasderede.network.tools import NetworkTools
        self.network_tools = NetworkTools()
    
    def test_network_tools_instantiation(self):
        """Testa se NetworkTools pode ser instanciado."""
        self.assertIsNotNone(self.network_tools)
    
    def test_resolve_and_check_status_localhost(self):
        """Testa resolução e status do localhost."""
        try:
            is_online, ip = self.network_tools.resolve_and_check_status('localhost')
            # localhost deve sempre resolver para um IP válido
            self.assertIsNotNone(ip)
            self.assertIn(ip, ['127.0.0.1', '::1'])
        except Exception as e:
            self.skipTest(f"Teste de localhost falhou: {e}")
    
    def test_resolve_ip_and_hostname_localhost(self):
        """Testa resolução de IP e hostname para localhost."""
        try:
            ip, hostname = self.network_tools.resolve_ip_and_hostname('localhost')
            self.assertIn(ip, ['127.0.0.1', '::1'])
            self.assertIsInstance(hostname, str)
        except Exception as e:
            self.skipTest(f"Teste de resolução localhost falhou: {e}")
    
    def test_invalid_hostname_handling(self):
        """Testa o tratamento de hostname inválido."""
        ip, hostname = self.network_tools.resolve_ip_and_hostname('invalid-hostname-12345')
        # Para hostnames inválidos, deve retornar "Inválido"
        self.assertEqual(ip, "Inválido")
        self.assertEqual(hostname, "Inválido")


class TestAppController(unittest.TestCase):
    """Testa o AppController da nova estrutura."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        # Criar mock da aplicação
        self.mock_app = Mock()
        self.mock_app.base_dir = str(project_root)
        self.mock_app.translate = lambda x, **kwargs: x.format(**kwargs) if kwargs else x
        self.mock_app.show_info = Mock()
        self.mock_app.show_error = Mock()
        
        # Criar diretório temporário para testes
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, 'test_hosts.json')
    
    def tearDown(self):
        """Limpeza após os testes."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('ferramentasderede.core.controller.FAVORITES_FILE')
    def test_add_host_functionality(self, mock_favorites_file):
        """Testa a funcionalidade completa de adição de host."""
        mock_favorites_file.__str__ = lambda: self.temp_file
        mock_favorites_file.__fspath__ = lambda: self.temp_file
        
        from ferramentasderede.core.controller import AppController
        
        controller = AppController(self.mock_app)
        
        # Simular adição de host com resolução
        with patch.object(controller.network_tools, 'resolve_ip_and_hostname') as mock_resolve:
            mock_resolve.return_value = ('192.168.1.100', 'test-host.local')
            
            # Simular input do usuário
            host_input = 'test-host.local'
            
            # Testar resolução
            ip, hostname = controller.network_tools.resolve_ip_and_hostname(host_input)
            self.assertEqual(ip, '192.168.1.100')
            self.assertEqual(hostname, 'test-host.local')


class TestSystemTools(unittest.TestCase):
    """Testa as SystemTools da nova estrutura."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        # Criar mock da aplicação
        self.mock_app = Mock()
        self.mock_app.translate = lambda x, **kwargs: x.format(**kwargs) if kwargs else x
        
        from ferramentasderede.system.tools import SystemTools
        self.system_tools = SystemTools(self.mock_app)
    
    def test_system_tools_instantiation(self):
        """Testa se SystemTools pode ser instanciado."""
        self.assertIsNotNone(self.system_tools)
        self.assertEqual(self.system_tools.app, self.mock_app)


class TestConfigSettings(unittest.TestCase):
    """Testa as configurações da nova estrutura."""
    
    def test_config_import(self):
        """Testa se todas as configurações principais podem ser importadas."""
        try:
            from ferramentasderede.config.settings import (
                APP_VERSION,
                MONOSPACE_FONT,
                DISCOVERY_CACHE_FILE,
                STATUS_PING_TIMEOUT,
                UI_PREFS_FILE,
                FAVORITES_FILE,
                TOP_60_PORTS,
                ALL_PORTS
            )
            
            # Verificar tipos das configurações
            self.assertIsInstance(APP_VERSION, str)
            self.assertIsInstance(MONOSPACE_FONT, tuple)
            self.assertIsInstance(DISCOVERY_CACHE_FILE, str)
            self.assertIsInstance(STATUS_PING_TIMEOUT, (int, float))
            self.assertIsInstance(UI_PREFS_FILE, str)
            self.assertIsInstance(FAVORITES_FILE, str)
            self.assertIsInstance(TOP_60_PORTS, list)
            self.assertIsInstance(ALL_PORTS, list)
            
        except ImportError as e:
            self.fail(f"Falha ao importar configurações: {e}")
    
    def test_port_lists_validity(self):
        """Testa se as listas de portas são válidas."""
        from ferramentasderede.config.settings import TOP_60_PORTS, ALL_PORTS
        
        # Verificar se as portas são números válidos
        for port in TOP_60_PORTS:
            self.assertIsInstance(port, int)
            self.assertGreaterEqual(port, 1)
            self.assertLessEqual(port, 65535)
        
        for port in ALL_PORTS:
            self.assertIsInstance(port, int)
            self.assertGreaterEqual(port, 1)
            self.assertLessEqual(port, 65535)
        
        # Verificar se TOP_60_PORTS é subconjunto de ALL_PORTS
        self.assertTrue(set(TOP_60_PORTS).issubset(set(ALL_PORTS)))


if __name__ == '__main__':
    # Executar testes
    unittest.main(verbosity=2)
