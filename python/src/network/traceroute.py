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


IPV4_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")

def traceroute_structured(target_ip, current_process_holder=None, source_ip=None, max_hops=30):
    """Executa traceroute com emissão de eventos JSON estruturados por salto (NDJSON).

    Enriquece cada salto descoberto com:
    - RTTs individuais e RTT médio
    - ASN (Sistema Autônomo BGP) via Team Cymru
    - Nome da Operadora / Provedor
    - Código do País
    """
    import json
    from src.network.asn_lookup import lookup_ip_asn

    logging.info(f"TRACEROUTE STRUCTURED: Iniciando para {target_ip} (src={source_ip or 'auto'})")
    hops_cap = max(1, min(int(max_hops or 30), 64))

    process = None
    try:
        if os.name == 'nt':
            command = ["tracert", "-h", str(hops_cap), "-w", "2500", target_ip]
            encoding = 'cp850'
            creationflags = subprocess.CREATE_NO_WINDOW
        else:
            command = ["traceroute", "-m", str(hops_cap), "-w", "3", target_ip]
            if source_ip:
                command = ["traceroute", "-m", str(hops_cap), "-w", "3", "-s", source_ip, target_ip]
            encoding = 'utf-8'
            creationflags = 0

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=encoding,
            errors='replace',
            creationflags=creationflags
        )

        if current_process_holder is not None:
            current_process_holder['_current_process'] = process

        yield json.dumps({"type": "start", "target": target_ip, "max_hops": hops_cap}) + "\n"

        hop_count = 0
        while True:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    break
                time.sleep(0.05)
                continue

            clean_line = line.strip()
            if not clean_line:
                continue

            # Parse de linha de salto
            m_hop = re.match(r"^(\d+)\s+", clean_line)
            if m_hop:
                hop_num = int(m_hop.group(1))
                remainder = clean_line[m_hop.end():]

                # RTTs
                tokens = re.findall(r"(?:<\s*1|\d+)\s*ms|\*", remainder)
                rtts = []
                for t in tokens:
                    if t == "*":
                        rtts.append(None)
                    else:
                        val = t.replace("ms", "").replace("<", "").strip()
                        rtts.append(float(val) if val else 0.5)

                valid_rtts = [r for r in rtts if r is not None]
                avg_rtt = round(sum(valid_rtts) / len(valid_rtts), 1) if valid_rtts else None

                # IP e Hostname
                ips = IPV4_RE.findall(remainder)
                ip = ips[-1] if ips else None

                hostname = None
                if ip and "[" in remainder and "]" in remainder:
                    host_match = re.search(r"([a-zA-Z0-9.-]+)\s+\[", remainder)
                    if host_match:
                        hostname = host_match.group(1)

                # Lookup ASN se IP disponível
                asn_info = lookup_ip_asn(ip) if ip else {"asn": "—", "as_name": "—", "country": "—"}

                hop_count += 1
                hop_data = {
                    "type": "hop",
                    "hop": hop_num,
                    "ip": ip or "*",
                    "hostname": hostname,
                    "rtts": rtts,
                    "avg_ms": avg_rtt,
                    "loss": len(valid_rtts) == 0,
                    "asn": asn_info.get("asn", "—"),
                    "as_name": asn_info.get("as_name", "—"),
                    "country": asn_info.get("country", "—"),
                    "raw_line": clean_line,
                }
                yield json.dumps(hop_data) + "\n"
            else:
                # Linhas informativas do cabeçalho ou rodapé
                yield json.dumps({"type": "info", "text": clean_line}) + "\n"

        yield json.dumps({"type": "done", "target": target_ip, "total_hops": hop_count}) + "\n"

    except Exception as e:
        logging.error(f"TRACEROUTE STRUCTURED erro: {e}")
        yield json.dumps({"type": "error", "error": str(e)}) + "\n"
    finally:
        if process:
            try:
                process.terminate()
                time.sleep(0.05)
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass
        if current_process_holder is not None:
            current_process_holder['_current_process'] = None

