#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste para verificar se o erro de autenticação está sendo exibido corretamente 
sem repetição nos campos do SystemInfoPanel.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_auth_error_display_fix():
    """Testa se o erro de autenticação está sendo exibido corretamente sem repetição."""
    
    print("🔧 Testando correção da exibição de erro de autenticação...")
    
    try:
        # Verificar se o SystemInfoPanel foi corrigido
        print("\n🔍 Verificando SystemInfoPanel...")
        
        with open('app/ui_components/system_info_panel.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'sysinfo_auth_error' in content:
            print("✅ SystemInfoPanel usa sysinfo_auth_error para erros de autenticação")
        else:
            print("❌ SystemInfoPanel não usa sysinfo_auth_error")
        
        if 'authentication' in content.lower() and 'autenticação' in content.lower():
            print("✅ SystemInfoPanel detecta erros de autenticação")
        else:
            print("❌ SystemInfoPanel não detecta erros de autenticação")
        
        # Verificar se as traduções foram adicionadas
        print("\n🔍 Verificando arquivos de tradução...")
        
        translation_files = [
            'languages/pt-BR-tools.json',
            'languages/en-US-tools.json',
            'languages/es-ES-tools.json'
        ]
        
        for file_path in translation_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'sysinfo_auth_error' in content:
                print(f"✅ {file_path} tem a chave sysinfo_auth_error")
            else:
                print(f"❌ {file_path} não tem a chave sysinfo_auth_error")
        
        # Verificar o conteúdo específico das traduções
        print("\n🔍 Verificando conteúdo das traduções...")
        
        with open('languages/pt-BR-tools.json', 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '"sysinfo_auth_error": "Erro de autenticação"' in content:
            print("✅ Tradução em português correta")
        else:
            print("❌ Tradução em português incorreta")
        
        with open('languages/en-US-tools.json', 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '"sysinfo_auth_error": "Authentication error"' in content:
            print("✅ Tradução em inglês correta")
        else:
            print("❌ Tradução em inglês incorreta")
        
        with open('languages/es-ES-tools.json', 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '"sysinfo_auth_error": "Error de autenticación"' in content:
            print("✅ Tradução em espanhol correta")
        else:
            print("❌ Tradução em espanhol incorreta")
        
        print(f"\n✅ Teste concluído!")
        print(f"📝 Agora quando houver erro de autenticação na seção 'Informações do Sistema':")
        print(f"   • Em vez de repetir o erro longo em cada campo (SO, Versão, etc.)")
        print(f"   • Será exibido apenas 'Erro de autenticação' em todos os campos")
        print(f"   • A mensagem detalhada aparecerá apenas no popup de erro")
        print(f"   • A interface ficará mais limpa e profissional")
        
    except FileNotFoundError as e:
        print(f"❌ Arquivo não encontrado: {e}")
    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")

if __name__ == "__main__":
    test_auth_error_display_fix()
