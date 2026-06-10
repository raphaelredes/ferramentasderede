import os
import subprocess
import logging
import time
import select
import re

def traceroute(target_ip, current_process_holder=None, source_ip=None):
    """Executa traceroute simples e robusto com timeout adequado.

    `source_ip` força a interface de saída (Windows: -S, Linux: -s).
    """
    logging.info(f"TRACEROUTE: Iniciando para {target_ip} (src={source_ip or 'auto'})")

    process = None
    try:
        if os.name == 'nt':
            # Windows tracert.exe `-S` is for IPv6 strict source-route, NOT
            # source-address (that flag does not exist in IPv4 tracert at
            # all). The legacy code added `-S <ip>` blindly, which either
            # tracert ignored or rejected with a usage banner — multi-VLAN
            # operators got silent fallback to the default route. Until we
            # wire PowerShell `Test-NetConnection -TraceRoute -SourceIPAddress`,
            # we log a warning and drop the flag so the trace still runs.
            command = ["tracert", "-h", "15", "-w", "3000"]
            command.append(target_ip)
            encoding = 'cp850'
            if source_ip:
                logging.warning(
                    "traceroute: source_ip=%r requested but Windows tracert does not support source-address; using default route.",
                    source_ip,
                )
        else:
            command = ["traceroute", "-m", "15", "-w", "3"]
            if source_ip:
                command += ["-s", source_ip]
            command.append(target_ip)
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

        # Honest, visible warning when the operator picked a source NIC but
        # the OS can't honor it for traceroute. Previously this was a silent
        # log line — the operator saw a normal trace and assumed it left via
        # the chosen VLAN when it actually used the default route.
        if source_ip and os.name == 'nt':
            yield (
                f"[AVISO] O Windows tracert não suporta IP de origem ({source_ip}); "
                f"a rota foi traçada pela interface padrão do SO, não pela NIC selecionada.\n\n"
            )
        
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
        except Exception as e:
            logging.debug(f"TRACEROUTE: post-loop status check failed: {e}")
            
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
            except Exception as e:
                logging.debug(f"TRACEROUTE: cleanup terminate/kill failed: {e}")
        
        if current_process_holder is not None:
            current_process_holder['_current_process'] = None
            
        logging.info(f"TRACEROUTE: Finalizado para {target_ip}")
