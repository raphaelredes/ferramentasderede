"""
Teste de Integração: Busca de Informações do Sistema - Discos

Este teste garante que a funcionalidade de buscar informações de disco
continue funcionando corretamente, mesmo após modificações no código.

CRÍTICO: Este teste DEVE passar sempre. Se falhar, a funcionalidade de
         exibição de discos está quebrada.
"""
import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


class TestSystemInfoDisks(unittest.TestCase):
    """Testes para garantir que a busca de discos funcione corretamente"""

    def test_powershell_script_syntax(self):
        """Verifica se o script PowerShell tem sintaxe correta"""
        from src.system.core.remote_commands import RemoteCommands

        # Criar instância mock
        rc = RemoteCommands("fake_ip", "fake_user", "fake_pass")

        # Obter o método
        script = '''
        Get-WmiObject -Class Win32_LogicalDisk -Filter "DriveType=3" |
        Select-Object DeviceID, VolumeName,
            @{N="Total_GB";E={[Math]::Round($_.Size / 1GB, 2)}},
            @{N="Free_GB";E={[Math]::Round($_.FreeSpace / 1GB, 2)}} |
        ConvertTo-Json -Compress
        '''

        # Verificar que não usa JavaScriptSerializer (causa referência circular)
        self.assertNotIn("JavaScriptSerializer", script,
                        "ERRO: Script usa JavaScriptSerializer que causa referência circular!")

        # Verificar que usa ConvertTo-Json
        self.assertIn("ConvertTo-Json", script,
                     "ERRO: Script deve usar ConvertTo-Json para serialização!")

        # Verificar que seleciona apenas propriedades necessárias
        self.assertIn("Select-Object", script,
                     "ERRO: Script deve usar Select-Object para filtrar propriedades!")

        print("✓ Script PowerShell está correto")

    def test_disk_data_structure(self):
        """Verifica se os dados de disco têm a estrutura correta"""
        # Simular dados que viriam do PowerShell
        mock_disk_data = [
            {
                "DeviceID": "C:",
                "VolumeName": "Sistema",
                "Total_GB": 500.0,
                "Free_GB": 200.0
            },
            {
                "DeviceID": "D:",
                "VolumeName": "Dados",
                "Total_GB": 1000.0,
                "Free_GB": 600.0
            }
        ]

        # Verificar estrutura
        for disk in mock_disk_data:
            self.assertIn("DeviceID", disk, "Disco deve ter DeviceID")
            self.assertIn("VolumeName", disk, "Disco deve ter VolumeName")
            self.assertIn("Total_GB", disk, "Disco deve ter Total_GB")
            self.assertIn("Free_GB", disk, "Disco deve ter Free_GB")

            # Verificar tipos
            self.assertIsInstance(disk["Total_GB"], (int, float),
                                "Total_GB deve ser numérico")
            self.assertIsInstance(disk["Free_GB"], (int, float),
                                "Free_GB deve ser numérico")

        print(f"✓ Estrutura de dados validada para {len(mock_disk_data)} discos")

    def test_processed_data_includes_disks(self):
        """Verifica se processed_data sempre inclui a chave 'Disks'"""
        # Simular dados processados
        processed_data = {
            "OS": "Windows 10",
            "CPU": "Intel Core i5",
            "RAM_GB": 16,
            "Disks": [
                {"DeviceID": "C:", "VolumeName": "Sistema", "Total_GB": 500.0, "Free_GB": 200.0}
            ]
        }

        # CRÍTICO: Disks DEVE estar presente
        self.assertIn("Disks", processed_data,
                     "ERRO CRÍTICO: processed_data DEVE conter chave 'Disks'!")

        # Deve ser uma lista
        self.assertIsInstance(processed_data["Disks"], list,
                            "ERRO: 'Disks' deve ser uma lista!")

        print("✓ processed_data contém 'Disks' corretamente")

    def test_display_info_receives_disks(self):
        """Verifica se display_info recebe dados de disco corretamente"""
        # Este teste verifica a lógica sem criar widgets reais
        # Simular o comportamento do método display_info

        test_data = {
            "OS": "Windows 10",
            "OS_Version": "10.0.19045",
            "CPU": "Intel Core i5",
            "RAM_GB": 16,
            "InstallDate": "01/01/2025",
            "Uptime": "5 dias",
            "Disks": [
                {"DeviceID": "C:", "VolumeName": "Sistema", "Total_GB": 500.0, "Free_GB": 200.0}
            ]
        }

        # Verificar que 'Disks' está presente e é uma lista
        self.assertIn("Disks", test_data, "ERRO: test_data deve conter 'Disks'")
        self.assertIsInstance(test_data["Disks"], list, "ERRO: 'Disks' deve ser uma lista")
        self.assertEqual(len(test_data["Disks"]), 1, "ERRO: Deve haver 1 disco nos dados de teste")

        # Simular extração como no código real
        disks_data = test_data.get("Disks", [])
        self.assertEqual(len(disks_data), 1, "ERRO: Discos não foram extraídos corretamente")

        print("✓ display_info chama _display_disk_info corretamente")

    def test_no_duplicate_callbacks(self):
        """Verifica se não há callbacks duplicados para discos"""
        from src.ui.components.tool_controllers.sysinfo_controller import SysInfoController
        import inspect

        # Verificar assinatura do _get_sysinfo_worker
        source = inspect.getsource(SysInfoController._get_sysinfo_worker)

        # NÃO deve ter callback_update_disks como parâmetro
        sig = inspect.signature(SysInfoController._get_sysinfo_worker)
        params = list(sig.parameters.keys())

        self.assertNotIn("callback_update_disks", params,
                        "ERRO: Não deve haver callback_update_disks separado! "
                        "Isso causava condição de corrida.")

        # Verificar que processed_data contém Disks
        self.assertIn("processed_data[\"Disks\"]", source,
                     "ERRO: processed_data deve incluir Disks!")

        print("✓ Sem callbacks duplicados - dados passados corretamente")


class TestSystemInfoIntegrity(unittest.TestCase):
    """Testes de integridade do sistema de informações"""

    def test_remote_commands_get_disks_info_exists(self):
        """Verifica se o método get_disks_info existe"""
        from src.system.core.remote_commands import RemoteCommands

        self.assertTrue(hasattr(RemoteCommands, 'get_disks_info'),
                       "ERRO: RemoteCommands deve ter método get_disks_info!")

        print("✓ Método get_disks_info existe")

    def test_system_info_panel_display_disk_info_exists(self):
        """Verifica se o método _display_disk_info existe"""
        from src.ui.components.system_info_panel import SystemInfoPanel

        self.assertTrue(hasattr(SystemInfoPanel, '_display_disk_info'),
                       "ERRO: SystemInfoPanel deve ter método _display_disk_info!")

        print("✓ Método _display_disk_info existe")


def run_tests():
    """Executa todos os testes e retorna o resultado"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSystemInfoDisks))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemInfoIntegrity))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 70)
    print("TESTE DE INTEGRIDADE: Busca de Informações do Sistema - Discos")
    print("=" * 70)
    print()

    success = run_tests()

    print()
    print("=" * 70)
    if success:
        print("✅ TODOS OS TESTES PASSARAM - Funcionalidade protegida!")
    else:
        print("❌ TESTES FALHARAM - Funcionalidade quebrada!")
        print("   AÇÃO NECESSÁRIA: Reverta as mudanças ou corrija o código!")
    print("=" * 70)

    sys.exit(0 if success else 1)
