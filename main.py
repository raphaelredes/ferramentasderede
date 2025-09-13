#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ferramentas de Rede - Aplicação Principal

Ponto de entrada principal da aplicação de gerenciamento de redes.
Aplicação profissional para monitoramento, diagnóstico e gerenciamento de redes.

Autor: Sistema de Ferramentas de Rede
Versão: 2.0.0
"""

import sys
import os
import logging
from pathlib import Path

# Adicionar o diretório src ao path para importar o pacote
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def setup_logging():
    """Configura o sistema de logging da aplicação."""
    log_dir = current_dir / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "app.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """Função principal da aplicação."""
    try:
        # Configurar logging
        setup_logging()
        logging.info("Iniciando aplicação Ferramentas de Rede v2.0.0")
        
        # Importar a aplicação principal
        from src.core import NetworkToolsApp
        
        # Configurar diretório base
        base_dir = str(current_dir)
        
        # Criar a aplicação
        logging.info("Criando instância da aplicação...")
        app = NetworkToolsApp(base_dir)
        logging.info("Instância criada com sucesso")
        
        # Executar a aplicação
        logging.info("Executando aplicação...")
        app.run()
        
        logging.info("Aplicação finalizada normalmente")
        
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        print("💡 Verifique se todos os módulos estão na estrutura correta.")
        logging.error(f"Erro de importação: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        logging.error(f"Erro na execução da aplicação: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()