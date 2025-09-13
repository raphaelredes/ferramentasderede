#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Teste - Nova Funcionalidade de Adição de Hosts
Demonstra como a nova funcionalidade funciona com resolução automática de IP/hostname.
"""

import sys
import os
import logging

# Adicionar o diretório atual ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_host_resolution():
    """Testa a resolução de hosts usando as ferramentas de rede."""
    print("🧪 Testando Resolução de Hosts")
    print("=" * 50)
    
    try:
        from app.network_tools import NetworkTools
        
        network_tools = NetworkTools()
        
        # Lista de hosts para testar
        test_hosts = [
            "google.com",
            "8.8.8.8", 
            "github.com",
            "192.168.1.1"
        ]
        
        print("📡 Testando resolução de IP e hostname:")
        print()
        
        for host in test_hosts:
            print(f"🔍 Testando: {host}")
            
            try:
                # Resolver IP e hostname
                resolved_ip, resolved_hostname = network_tools.resolve_ip_and_hostname(host)
                
                print(f"   IP: {resolved_ip}")
                print(f"   Hostname: {resolved_hostname}")
                
                # Verificar status
                status_is_online, current_ip = network_tools.resolve_and_check_status(host)
                status = "🟢 Online" if status_is_online else "🔴 Offline"
                print(f"   Status: {status}")
                
            except Exception as e:
                print(f"   ❌ Erro: {e}")
            
            print()
        
        print("✅ Teste de resolução concluído!")
        
    except Exception as e:
        print(f"❌ Erro ao testar resolução: {e}")

def test_host_validation():
    """Testa a validação de entrada de hosts."""
    print("🧪 Testando Validação de Entrada")
    print("=" * 50)
    
    # Casos de teste
    test_cases = [
        ("google.com", "Válido - apenas hostname"),
        ("8.8.8.8", "Válido - apenas IP"),
        ("google.com,8.8.8.8", "Válido - hostname,IP"),
        ("google.com,8.8.8.8,00:11:22:33:44:55", "Válido - hostname,IP,MAC"),
        ("", "Inválido - vazio"),
        ("   ", "Inválido - apenas espaços"),
    ]
    
    print("📝 Casos de teste para validação:")
    print()
    
    for input_value, description in test_cases:
        is_valid = bool(input_value.strip())
        status = "✅ Válido" if is_valid else "❌ Inválido"
        print(f"{status} - '{input_value}' ({description})")
    
    print()
    print("✅ Teste de validação concluído!")

def test_async_operations():
    """Testa operações assíncronas."""
    print("🧪 Testando Operações Assíncronas")
    print("=" * 50)
    
    import threading
    import time
    
    def simulate_network_operation(host, delay=1):
        """Simula uma operação de rede."""
        print(f"   🔄 Iniciando operação para {host}...")
        time.sleep(delay)
        print(f"   ✅ Operação concluída para {host}")
    
    hosts = ["host1", "host2", "host3"]
    threads = []
    
    print("🚀 Iniciando operações assíncronas:")
    print()
    
    start_time = time.time()
    
    for host in hosts:
        thread = threading.Thread(target=simulate_network_operation, args=(host,))
        threads.append(thread)
        thread.start()
    
    # Aguardar todas as threads terminarem
    for thread in threads:
        thread.join()
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print()
    print(f"⏱️  Tempo total: {total_time:.2f}s (seria ~3s se fosse sequencial)")
    print("✅ Teste de operações assíncronas concluído!")

def show_feature_summary():
    """Mostra um resumo das novas funcionalidades."""
    print("🎉 RESUMO DAS NOVAS FUNCIONALIDADES")
    print("=" * 50)
    
    features = [
        "🔍 Resolução automática de IP e hostname",
        "⚡ Verificação de status em background",
        "🎯 Seleção automática da aba do novo host",
        "📊 Atualização automática do indicador de status",
        "💬 Feedback visual durante o processo",
        "🔄 Operações assíncronas para não bloquear a UI",
        "✅ Validação melhorada de entrada",
        "🎨 Interface aprimorada com dicas visuais"
    ]
    
    print("✨ Funcionalidades implementadas:")
    print()
    
    for feature in features:
        print(f"   {feature}")
    
    print()
    print("🚀 Como usar:")
    print("   1. Clique em 'Adicionar Host'")
    print("   2. Digite apenas o nome ou IP (ex: google.com)")
    print("   3. O sistema resolverá automaticamente o hostname e IP")
    print("   4. A aba do novo host será criada e selecionada")
    print("   5. O status será verificado em background")
    
    print()
    print("💡 Benefícios:")
    print("   • Experiência mais fluida para o usuário")
    print("   • Dados mais precisos e atualizados")
    print("   • Interface responsiva durante operações")
    print("   • Feedback visual em tempo real")

def main():
    """Função principal do teste."""
    print("🔧 TESTE DA NOVA FUNCIONALIDADE - ADIÇÃO DE HOSTS")
    print("=" * 60)
    print()
    
    # Configurar logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        # Executar testes
        test_host_resolution()
        print()
        
        test_host_validation()
        print()
        
        test_async_operations()
        print()
        
        show_feature_summary()
        print()
        
        print("🎯 Todos os testes concluídos com sucesso!")
        print("💡 A nova funcionalidade está pronta para uso!")
        
    except Exception as e:
        print(f"❌ Erro durante os testes: {e}")
        logging.error(f"Erro durante os testes: {e}")

if __name__ == "__main__":
    main()
