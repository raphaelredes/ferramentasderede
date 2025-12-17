#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Otimizador de Performance para Operações de Rede
Implementa técnicas avançadas para otimizar operações de rede como ping, port scanning, etc.
"""

import socket
import subprocess
import threading
import time
import queue
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional, Any
import logging
import os
import ipaddress
from functools import lru_cache

class NetworkPerformanceOptimizer:
    """
    Otimizador de performance para operações de rede.
    """
    
    def __init__(self):
        self._dns_cache = {}
        self._ping_cache = {}
        self._port_cache = {}
        self._connection_pool = {}
        self._timeout_cache = {}
        
        # Configurações de performance
        self.max_concurrent_pings = 20
        self.max_concurrent_scans = 30
        self.ping_timeout = 1.0
        self.scan_timeout = 0.5
        self.cache_ttl = 300  # 5 minutos
        
        # Inicializar pools de threads
        self._ping_executor = ThreadPoolExecutor(max_workers=self.max_concurrent_pings, thread_name_prefix="PingWorker")
        self._scan_executor = ThreadPoolExecutor(max_workers=self.max_concurrent_scans, thread_name_prefix="ScanWorker")
        
        # Iniciar limpeza de cache
        self._start_cache_cleanup()
    
    def _start_cache_cleanup(self):
        """Inicia thread de limpeza de cache."""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(60)  # Limpar a cada minuto
                    self._cleanup_expired_cache()
                except Exception as e:
                    logging.error(f"Error in cache cleanup: {e}")
        
        thread = threading.Thread(target=cleanup_worker, daemon=True, name="CacheCleanup")
        thread.start()
    
    def _cleanup_expired_cache(self):
        """Remove entradas expiradas do cache."""
        current_time = time.time()
        
        # Limpar cache de DNS
        expired_keys = [k for k, (_, timestamp) in self._dns_cache.items() 
                       if current_time - timestamp > self.cache_ttl]
        for key in expired_keys:
            del self._dns_cache[key]
        
        # Limpar cache de ping
        expired_keys = [k for k, (_, timestamp) in self._ping_cache.items() 
                       if current_time - timestamp > self.cache_ttl]
        for key in expired_keys:
            del self._ping_cache[key]
        
        # Limpar cache de portas
        expired_keys = [k for k, (_, timestamp) in self._port_cache.items() 
                       if current_time - timestamp > self.cache_ttl]
        for key in expired_keys:
            del self._port_cache[key]
        
        if expired_keys:
            logging.debug(f"Cleaned {len(expired_keys)} expired cache entries")
    
    @lru_cache(maxsize=1000)
    def resolve_hostname(self, hostname: str) -> Optional[str]:
        """Resolve hostname com cache otimizado."""
        cache_key = hostname.lower()
        
        if cache_key in self._dns_cache:
            ip, timestamp = self._dns_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return ip
        
        try:
            ip = socket.gethostbyname(hostname)
            self._dns_cache[cache_key] = (ip, time.time())
            return ip
        except socket.gaierror:
            return None
        except Exception as e:
            logging.error(f"Error resolving hostname {hostname}: {e}")
            return None
    
    def batch_ping_hosts(self, hosts: List[str], callback=None) -> Dict[str, Dict[str, Any]]:
        """Executa ping em lote para múltiplos hosts de forma otimizada."""
        results = {}
        
        def ping_worker(host):
            """Worker para ping de um host."""
            try:
                result = self._ping_host_optimized(host)
                if callback:
                    callback(host, result)
                return host, result
            except Exception as e:
                error_result = {"online": False, "error": str(e), "ip": None}
                if callback:
                    callback(host, error_result)
                return host, error_result
        
        # Executar pings em paralelo
        futures = {self._ping_executor.submit(ping_worker, host): host for host in hosts}
        
        for future in as_completed(futures):
            host = futures[future]
            try:
                host, result = future.result(timeout=self.ping_timeout + 1)
                results[host] = result
            except Exception as e:
                results[host] = {"online": False, "error": str(e), "ip": None}
        
        return results
    
    def _ping_host_optimized(self, host: str) -> Dict[str, Any]:
        """Ping otimizado para um host."""
        cache_key = host.lower()
        
        # Verificar cache
        if cache_key in self._ping_cache:
            result, timestamp = self._ping_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return result
        
        # Resolver IP
        ip = self.resolve_hostname(host)
        if not ip:
            result = {"online": False, "error": "DNS resolution failed", "ip": None}
            self._ping_cache[cache_key] = (result, time.time())
            return result
        
        # Executar ping
        try:
            param_count = '-n' if os.name == 'nt' else '-c'
            param_timeout = '-w' if os.name == 'nt' else '-W'
            timeout_val = str(int(self.ping_timeout * 1000)) if os.name == 'nt' else str(self.ping_timeout)
            
            command = ["ping", param_count, "1", param_timeout, timeout_val, ip]
            result = subprocess.run(
                command, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL, 
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=self.ping_timeout + 1
            )
            
            ping_result = {
                "online": result.returncode == 0,
                "ip": ip,
                "error": None
            }
            
            # Cache do resultado
            self._ping_cache[cache_key] = (ping_result, time.time())
            return ping_result
            
        except subprocess.TimeoutExpired:
            result = {"online": False, "error": "Timeout", "ip": ip}
            self._ping_cache[cache_key] = (result, time.time())
            return result
        except Exception as e:
            result = {"online": False, "error": str(e), "ip": ip}
            self._ping_cache[cache_key] = (result, time.time())
            return result
    
    def batch_port_scan(self, target: str, ports: List[int], callback=None) -> Dict[int, Dict[str, Any]]:
        """Executa escaneamento de portas em lote de forma otimizada."""
        results = {}
        
        def scan_worker(port):
            """Worker para scan de uma porta."""
            try:
                result = self._scan_port_optimized(target, port)
                if callback:
                    callback(port, result)
                return port, result
            except Exception as e:
                error_result = {"open": False, "error": str(e)}
                if callback:
                    callback(port, error_result)
                return port, error_result
        
        # Executar scans em paralelo
        futures = {self._scan_executor.submit(scan_worker, port): port for port in ports}
        
        for future in as_completed(futures):
            port = futures[future]
            try:
                port, result = future.result(timeout=self.scan_timeout + 1)
                results[port] = result
            except Exception as e:
                results[port] = {"open": False, "error": str(e)}
        
        return results
    
    def _scan_port_optimized(self, target: str, port: int) -> Dict[str, Any]:
        """Scan otimizado para uma porta."""
        cache_key = f"{target}:{port}"
        
        # Verificar cache
        if cache_key in self._port_cache:
            result, timestamp = self._port_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return result
        
        # Resolver IP se necessário
        try:
            ip = ipaddress.ip_address(target)
            scan_ip = str(ip)
        except ValueError:
            scan_ip = self.resolve_hostname(target)
            if not scan_ip:
                result = {"open": False, "error": "Invalid target"}
                self._port_cache[cache_key] = (result, time.time())
                return result
        
        # Executar scan
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.scan_timeout)
            
            result_code = sock.connect_ex((scan_ip, port))
            sock.close()
            
            scan_result = {
                "open": result_code == 0,
                "error": None,
                "service": self._get_service_name(port) if result_code == 0 else None
            }
            
            # Cache do resultado
            self._port_cache[cache_key] = (scan_result, time.time())
            return scan_result
            
        except Exception as e:
            result = {"open": False, "error": str(e)}
            self._port_cache[cache_key] = (result, time.time())
            return result
    
    def _get_service_name(self, port: int) -> Optional[str]:
        """Obtém o nome do serviço para uma porta."""
        common_services = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
            80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
            993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1723: "PPTP",
            3306: "MySQL", 3389: "RDP", 5900: "VNC", 8080: "HTTP-Alt"
        }
        return common_services.get(port, "Unknown")
    
    def optimize_network_discovery(self, network_range: str) -> List[str]:
        """Otimiza descoberta de rede."""
        try:
            network = ipaddress.IPv4Network(network_range, strict=False)
            return [str(ip) for ip in network.hosts()]
        except Exception as e:
            logging.error(f"Error optimizing network discovery: {e}")
            return []
    
    def get_adaptive_timeout(self, operation_type: str, base_timeout: float = 1.0) -> float:
        """Retorna timeout adaptativo baseado no tipo de operação e histórico."""
        cache_key = f"timeout_{operation_type}"
        
        if cache_key in self._timeout_cache:
            return self._timeout_cache[cache_key]
        
        # Timeouts adaptativos baseados no tipo de operação
        timeouts = {
            "ping": 1.0,
            "port_scan": 0.5,
            "dns_resolve": 2.0,
            "connection": 3.0
        }
        
        timeout = timeouts.get(operation_type, base_timeout)
        self._timeout_cache[cache_key] = timeout
        return timeout
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de performance."""
        return {
            "dns_cache_size": len(self._dns_cache),
            "ping_cache_size": len(self._ping_cache),
            "port_cache_size": len(self._port_cache),
            "active_ping_workers": len([f for f in self._ping_executor._threads if f.is_alive()]),
            "active_scan_workers": len([f for f in self._scan_executor._threads if f.is_alive()]),
            "max_concurrent_pings": self.max_concurrent_pings,
            "max_concurrent_scans": self.max_concurrent_scans
        }
    
    def cleanup(self):
        """Limpa recursos do otimizador."""
        try:
            # Parar executors
            self._ping_executor.shutdown(wait=True, timeout=5)
            self._scan_executor.shutdown(wait=True, timeout=5)
            
            # Limpar caches
            self._dns_cache.clear()
            self._ping_cache.clear()
            self._port_cache.clear()
            self._connection_pool.clear()
            self._timeout_cache.clear()
            
            logging.debug("Network performance optimizer cleanup completed")
            
        except Exception as e:
            logging.error(f"Error during network performance optimizer cleanup: {e}")


# Instância global do otimizador de rede
network_optimizer = NetworkPerformanceOptimizer()

def get_network_optimizer():
    """Retorna a instância do otimizador de rede."""
    return network_optimizer
