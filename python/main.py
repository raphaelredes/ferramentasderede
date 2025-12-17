#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher de Desenvolvimento
---------------------------
Este script substitui o antigo main.py para alinhar o fluxo de desenvolvimento
com o start_dev.ps1.

Ele realiza:
1. Limpeza da porta 8000 (mata processos travados do backend).
2. Inicialização do ambiente Electron + Vite (que por sua vez inicia o backend).
"""

import os
import sys
import subprocess
import time
import platform
from pathlib import Path

def kill_process_on_port(port):
    """Mata o processo escutando na porta especificada."""
    print(f"🔍 [1/2] Verificando porta {port}...")
    
    try:
        if platform.system() == "Windows":
            # Encontrar PID usando netstat
            # netstat -ano | findstr :8000
            cmd = f"netstat -ano | findstr :{port}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        # Verificar se é TCP e se está LISTENING (opcional, mas bom)
                        if "LISTENING" in line or "ESTABLISHED" in line: # start_dev mata qualquer coisa na porta
                            print(f"💥 Matando processo {pid} que está usando a porta {port}...")
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Linux/Mac (lsof ou fuser)
            cmd = f"lsof -t -i:{port}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout:
                pids = result.stdout.strip().split()
                for pid in pids:
                    print(f"💥 Matando processo {pid}...")
                    subprocess.run(f"kill -9 {pid}", shell=True)
                    
    except Exception as e:
        print(f"⚠️ Erro ao tentar limpar porta {port}: {e}")
    
    print(f"✅ Porta {port} livre.")

def main():
    print("=== 🚀 Iniciando Ambiente de Desenvolvimento (via main.py) ===")
    
    # 1. Limpar porta 8000
    kill_process_on_port(8000)
    
    # 2. Definir caminhos
    current_dir = Path(__file__).parent.absolute()
    # main.py está em /python, precisamos ir para /electron
    # Estrutura:
    # root/
    #   electron/
    #   python/main.py
    
    electron_dir = current_dir.parent / "electron"
    
    if not electron_dir.exists():
        print(f"❌ Erro: Diretório 'electron' não encontrado em {electron_dir}")
        sys.exit(1)
        
    print(f"📂 Navegando para: {electron_dir}")
    print("✨ [2/2] Iniciando 'npm run dev'...")
    print("-------------------------------------------------------")
    
    # 3. Executar npm run dev
    # Shell=True é necessário para encontrar o npm no path do Windows
    try:
        subprocess.run("npm run dev", cwd=electron_dir, shell=True)
    except KeyboardInterrupt:
        print("\n🛑 Interrompido pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro ao executar npm run dev: {e}")

if __name__ == "__main__":
    main()