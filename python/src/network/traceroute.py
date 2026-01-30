import os
import subprocess
import logging
import time
import select
import re

def traceroute(target_ip, current_process_holder=None):
    """Executa traceroute simples e robusto com timeout adequado."""
    logging.info(f"TRACEROUTE: Iniciando para {target_ip}")
    
    process = None
    try:
        # Comando traceroute para Windows e Linux
        if os.name == 'nt':
            # No Windows: tracert com máximo de saltos limitado para hosts locais
            command = ["tracert", "-h", "15", "-w", "3000", target_ip]
            encoding = 'cp850'
        else:
            command = ["traceroute", "-m", "15", "-w", "3", target_ip]
            encoding = 'utf-8'
        
        # Executar comando com timeout
        process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding=encoding, 
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Armazenar referência do processo se um holder for fornecido
        if current_process_holder is not None:
            current_process_holder['_current_process'] = process
        
        yield f"Rastreando rota para {target_ip}...\n\n"
        
        # Ler output linha por linha
        line_count = 0
        
        while True:
            # Verificar se processo ainda está rodando
            if process.poll() is not None:
                # Processo terminou, ler linhas restantes
                remaining_lines = process.stdout.read()
                if remaining_lines:
                    yield remaining_lines
                break
                
            try:
                # Tentar ler linha com timeout pequeno
                if os.name == 'nt':
                    # No Windows, usar readline normal
                    line = process.stdout.readline()
                else:
                    # No Linux, usar select para timeout
                    ready, _, _ = select.select([process.stdout], [], [], 1.0)
                    if ready:
                        line = process.stdout.readline()
                    else:
                        line = None
                        
                if line:
                    yield line
                    line_count += 1
                else:
                    # Aguardar um pouco antes de tentar novamente
                    time.sleep(0.1)
                    
            except Exception as read_error:
                logging.error(f"TRACEROUTE: Erro na leitura: {read_error}")
                break
        
        # Finalização
        try:
            return_code = process.poll()
            if return_code is not None:
                if return_code == 0:
                    yield f"\nTraceroute concluído.\n"
                else:
                    yield f"\nTraceroute finalizado (código: {return_code}).\n"
            else:
                yield f"\nTraceroute interrompido.\n"
        except:
            pass
            
    except FileNotFoundError:
        yield f"Erro: Comando traceroute não encontrado no sistema.\n"
        yield f"No Windows: use 'tracert'. No Linux: instale 'traceroute'.\n"
    except Exception as e:
        logging.error(f"TRACEROUTE: Erro para {target_ip}: {e}")
        yield f"Erro no traceroute: {str(e)}\n"
    finally:
        # Limpeza forçada
        if process:
            try:
                process.terminate()
                time.sleep(0.1)
                if process.poll() is None:
                    process.kill()
            except:
                pass
        
        if current_process_holder is not None:
            current_process_holder['_current_process'] = None
            
        logging.info(f"TRACEROUTE: Finalizado para {target_ip}")
