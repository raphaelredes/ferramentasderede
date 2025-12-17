#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para limpar o cache de bytecode do Python e resolver problemas de importação.
Execute este script quando encontrar erros de importação inexplicáveis.
"""

import os
import sys
import shutil
import compileall

def clean_python_cache():
    """Remove todos os arquivos __pycache__ e .pyc do projeto."""
    print("🧹 Limpando cache do Python...")
    
    # Contador de arquivos removidos
    removed_count = 0
    
    # Percorre todos os diretórios do projeto
    for root, dirs, files in os.walk('.'):
        # Remove diretórios __pycache__
        for dir_name in dirs[:]:  # Cria uma cópia da lista para modificação segura
            if dir_name == '__pycache__':
                cache_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(cache_path)
                    print(f"  ✅ Removido: {cache_path}")
                    removed_count += 1
                except Exception as e:
                    print(f"  ❌ Erro ao remover {cache_path}: {e}")
                dirs.remove(dir_name)  # Remove da lista para não processar novamente
        
        # Remove arquivos .pyc
        for file_name in files:
            if file_name.endswith('.pyc'):
                pyc_path = os.path.join(root, file_name)
                try:
                    os.remove(pyc_path)
                    print(f"  ✅ Removido: {pyc_path}")
                    removed_count += 1
                except Exception as e:
                    print(f"  ❌ Erro ao remover {pyc_path}: {e}")
    
    print(f"\n📊 Total de arquivos de cache removidos: {removed_count}")
    return removed_count

def recompile_python_files():
    """Recompila todos os arquivos Python do projeto."""
    print("\n🔨 Recompilando arquivos Python...")
    
    try:
        # Compila todos os arquivos Python do diretório atual
        result = compileall.compile_dir('.', force=True, quiet=1)
        
        if result:
            print("  ✅ Todos os arquivos Python foram recompilados com sucesso!")
        else:
            print("  ⚠️  Alguns arquivos não puderam ser recompilados.")
            
    except Exception as e:
        print(f"  ❌ Erro durante a recompilação: {e}")
        return False
    
    return True

def test_imports():
    """Testa as importações principais do projeto."""
    print("\n🧪 Testando importações principais...")
    
    test_imports = [
        "app.gui",
        "app.config", 
        "app.app_controller",
        "app.app_ui_manager",
        "app.translation_manager",
        "app.app_settings_manager",
        "app.performance_optimizer",
        "app.ui_components.base_dialog",
        "app.ui_components.custom_dialogs",
        "app.ui_components.credential_service",
        "app.ui_components.loading_window",
        "app.ui_components.welcome_dialog"
    ]
    
    failed_imports = []
    
    for module_name in test_imports:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name}")
        except Exception as e:
            print(f"  ❌ {module_name}: {e}")
            failed_imports.append((module_name, str(e)))
    
    if failed_imports:
        print(f"\n⚠️  {len(failed_imports)} importação(ões) falharam:")
        for module_name, error in failed_imports:
            print(f"    - {module_name}: {error}")
        return False
    else:
        print("\n🎉 Todas as importações foram bem-sucedidas!")
        return True

def main():
    """Função principal do script."""
    print("🚀 Iniciando limpeza e verificação do projeto...")
    print("=" * 50)
    
    # Limpa o cache
    removed_count = clean_python_cache()
    
    # Recompila os arquivos
    recompile_success = recompile_python_files()
    
    # Testa as importações
    imports_success = test_imports()
    
    print("\n" + "=" * 50)
    print("📋 Resumo da operação:")
    print(f"  • Arquivos de cache removidos: {removed_count}")
    print(f"  • Recompilação: {'✅ Sucesso' if recompile_success else '❌ Falha'}")
    print(f"  • Importações: {'✅ Sucesso' if imports_success else '❌ Falha'}")
    
    if recompile_success and imports_success:
        print("\n🎉 Projeto limpo e funcionando corretamente!")
        print("💡 Você pode agora executar 'python main.py' sem problemas.")
    else:
        print("\n⚠️  Alguns problemas foram encontrados.")
        print("💡 Verifique as mensagens de erro acima.")
    
    return recompile_success and imports_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
