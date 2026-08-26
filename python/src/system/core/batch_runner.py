# python/src/system/core/batch_runner.py
"""Módulo de execução concorrente de comandos WinRM em múltiplos hosts (Batch Runner).

Executa scripts PowerShell/CMD em múltiplos hosts em paralelo utilizando
ThreadPoolExecutor com credenciais associadas ou do Cofre.
"""

import time
import logging
import concurrent.futures
from typing import List, Dict, Any, Optional
from src.system.core.winrm_handler import WinRMHandler

def execute_batch_command(
    targets: List[Dict[str, Any]],
    command: str,
    max_workers: int = 10,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    """Executa um comando remotamente em múltiplos alvos em paralelo."""
    results = []

    def _execute_single_target(target_info: Dict[str, Any]) -> Dict[str, Any]:
        host = target_info.get("ip") or target_info.get("name")
        username = target_info.get("username")
        password = target_info.get("password")
        port = target_info.get("port", 5985)
        use_ssl = target_info.get("use_ssl", False)
        auth = target_info.get("auth", "ntlm")

        start_time = time.perf_counter()
        
        try:
            handler = WinRMHandler(
                host=host,
                username=username,
                password=password,
                port=port,
                use_ssl=use_ssl,
                auth=auth
            )
            
            output, error, status_code = handler.execute_command(command, timeout=timeout)
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            
            return {
                "host": host,
                "name": target_info.get("name", host),
                "success": (status_code == 0 and not error),
                "status_code": status_code,
                "stdout": output,
                "stderr": error,
                "elapsed_ms": elapsed
            }
        except Exception as exc:
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "host": host,
                "name": target_info.get("name", host),
                "success": False,
                "status_code": -1,
                "stdout": "",
                "stderr": str(exc),
                "elapsed_ms": elapsed
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(targets) or 1)) as executor:
        future_to_target = {executor.submit(_execute_single_target, t): t for t in targets}
        for future in concurrent.futures.as_completed(future_to_target):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                logging.debug(f"Erro na execução da thread batch: {e}")

    return results
