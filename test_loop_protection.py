#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste do sistema de proteção contra loops
"""

import sys
import os
import logging
import threading
import time
from pathlib import Path

# Adicionar o diretório src ao path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def setup_logging():
    """Configura o sistema de logging."""
    log_dir = current_dir / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "loop_test.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def simulate_callback_loop(app):
    """Simula um loop de callbacks para testar o sistema de proteção."""
    logging.info("=== INICIANDO TESTE DE LOOP DE CALLBACKS ===")
    
    def callback_spam():
        """Gera muitos callbacks para simular loop."""
        try:
            for i in range(2000):  # Mais que o threshold de 1000
                if not hasattr(app, '_loop_active') or not app._loop_active:
                    break
                app.after_idle(lambda: None)  # Callback vazio
                if i % 100 == 0:
                    logging.info(f"Callbacks gerados: {i}")
                time.sleep(0.001)  # 1ms delay
        except Exception as e:
            logging.error(f"Erro no spam de callbacks: {e}")
    
    # Agendar teste em 5 segundos
    threading.Timer(5.0, callback_spam).start()

def simulate_mainloop_freeze(app):
    """Simula travamento do mainloop para testar watchdog."""
    logging.info("=== INICIANDO TESTE DE TRAVAMENTO DO MAINLOOP ===")
    
    def freeze_mainloop():
        """Bloqueia o mainloop por mais de 10 segundos."""
        logging.info("Bloqueando mainloop...")
        try:
            # Simular operação bloqueante
            time.sleep(15)  # Mais que o timeout de 10 segundos
        except Exception as e:
            logging.error(f"Erro no freeze: {e}")
    
    # Agendar teste em 10 segundos
    def schedule_freeze():
        app.after(0, freeze_mainloop)
    
    threading.Timer(10.0, schedule_freeze).start()

def main():
    """Função principal do teste."""
    setup_logging()
    logging.info("Iniciando teste do sistema de proteção contra loops")
    
    try:
        from src.core import NetworkToolsApp
        
        # Criar aplicação
        base_dir = str(current_dir)
        app = NetworkToolsApp(base_dir)
        
        # Configurar testes
        test_mode = input("Escolha o teste (1=callback_loop, 2=mainloop_freeze, 3=ambos): ")
        
        if test_mode in ['1', '3']:
            simulate_callback_loop(app)
        
        if test_mode in ['2', '3']:
            simulate_mainloop_freeze(app)
        
        if test_mode not in ['1', '2', '3']:
            logging.info("Executando aplicação normal (sem teste de loop)")
        
        # Executar aplicação
        app.run()
        
    except Exception as e:
        logging.error(f"Erro no teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()