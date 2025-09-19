#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ferramentas de Rede - Aplicação Principal

Ponto de entrada principal da aplicação de gerenciamento de redes.
Aplicação profissional para monitoramento, diagnóstico e gerenciamento de redes.

Autor: Sistema de Ferramentas de Rede
Versão: 1.1.0
"""

import sys
import os
import logging
import signal
from pathlib import Path

# Adicionar o diretório src ao path para importar o pacote
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def setup_signal_handlers():
    """Configura handlers para sinais do sistema (Ctrl+C, etc.)."""
    def signal_handler(signum, frame):
        logging.info(f"Recebido sinal {signum}. Finalizando aplicação...")
        try:
            # Tentar finalização limpa primeiro
            import threading
            active_threads = [t for t in threading.enumerate() if not t.daemon]
            logging.debug(f"Threads ativas durante sinal: {[t.name for t in active_threads]}")

            # Forçar saída após breve delay
            import time
            time.sleep(0.1)

        except Exception as e:
            logging.error(f"Erro durante handler de sinal: {e}")

        # Saída forçada
        logging.info("Forçando saída da aplicação")
        os._exit(0)

    # Configurar handlers para diferentes sinais
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)  # Terminate

    logging.debug("Signal handlers configurados")

def setup_logging():
    """Configura o sistema de logging da aplicação."""
    log_dir = current_dir / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "app.log"
    
    logging.basicConfig(
        level=logging.DEBUG,  # Ativar debug para ver ajustes de altura
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
        logging.info("Iniciando aplicação Ferramentas de Rede v1.1.0")

        # Configurar signal handlers para finalização robusta
        setup_signal_handlers()

        # Importar a aplicação principal e o sistema de carregamento
        from src.core import NetworkToolsApp
        from src.ui.components.startup_loading_window import StartupManager

        # Configurar diretório base
        base_dir = str(current_dir)

        # Criar gerenciador de inicialização
        logging.info("Iniciando aplicação com janela de carregamento...")
        startup_manager = StartupManager(NetworkToolsApp, base_dir)

        # Iniciar aplicação com janela de carregamento
        startup_manager.start_application()

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