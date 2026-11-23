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
        username = target_info.get("username") or ""
        password = target_info.get("password") or ""

        start_time = time.perf_counter()
        if not host or not username or not password:
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "host": host or "",
                "name": target_info.get("name", host or ""),
                "success": False,
                "status_code": -1,
                "stdout": "",
                "stderr": "Credenciais ou endereço de destino ausentes.",
                "elapsed_ms": elapsed,
            }

        handler = None
        try:
            handler = WinRMHandler(
                target_ip=host,
                username=username,
                password=password,
            )
            conn_res = handler.connect()
            if "error" in conn_res:
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                return {
                    "host": host,
                    "name": target_info.get("name", host),
                    "success": False,
                    "status_code": -1,
                    "stdout": "",
                    "stderr": str(conn_res.get("error", "Falha na conexão WinRM.")),
                    "elapsed_ms": elapsed,
                }

            exec_res = handler.execute_script(command)
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            if exec_res.get("success"):
                raw_out = exec_res.get("output") or []
                stdout = "\n".join(str(line) for line in raw_out)
                return {
                    "host": host,
                    "name": target_info.get("name", host),
                    "success": True,
                    "status_code": 0,
                    "stdout": stdout,
                    "stderr": "",
                    "elapsed_ms": elapsed,
                }

            return {
                "host": host,
                "name": target_info.get("name", host),
                "success": False,
                "status_code": 1,
                "stdout": "",
                "stderr": str(exec_res.get("error", "Erro ao executar script remoto.")),
                "elapsed_ms": elapsed,
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
                "elapsed_ms": elapsed,
            }
        finally:
            if handler is not None:
                try:
                    handler.close()
                except Exception:
                    pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(targets) or 1)) as executor:
        future_to_target = {executor.submit(_execute_single_target, t): t for t in targets}
        for future in concurrent.futures.as_completed(future_to_target):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                logging.debug(f"Erro na execução da thread batch: {e}")

    return results
