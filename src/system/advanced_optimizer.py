#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Otimizador de Performance Avançado
Implementa técnicas modernas de otimização para melhorar significativamente a performance da aplicação.
"""

import asyncio
import threading
import time
import weakref
import gc
import psutil
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache, wraps
from typing import Dict, Any, Optional, Callable, List
import logging
import customtkinter as ctk

class AdvancedPerformanceOptimizer:
    """
    Otimizador de performance avançado com técnicas modernas.
    """
    
    def __init__(self, app):
        self.app = weakref.ref(app)
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="PerfOpt")
        self._ui_queue = queue.Queue()
        self._cache = {}
        self._debounce_timers = {}
        self._throttle_timers = {}
        self._background_tasks = []
        
        # Configurações de performance
        self.max_cache_size = 1000
        self.ui_update_interval = 0.016  # ~60 FPS
        self.memory_threshold = 150  # MB
        self.cpu_threshold = 80  # %
        
        # Inicializar otimizações
        self._setup_ui_optimizations()
        self._setup_memory_management()
        self._setup_cpu_monitoring()
    
    def _setup_ui_optimizations(self):
        """Configura otimizações específicas para UI."""
        app = self.app()
        if not app:
            return
        
        # Configurar atualizações de UI em batch
        self._ui_update_running = False
        self._pending_ui_updates = []
        
        # Iniciar thread de processamento de UI
        self._ui_thread = threading.Thread(target=self._ui_worker, daemon=True)
        self._ui_thread.start()
    
    def _ui_worker(self):
        """Worker thread para processar atualizações de UI de forma otimizada."""
        while True:
            try:
                # Processar atualizações em batch
                updates = []
                while len(updates) < 10:  # Máximo 10 updates por batch
                    try:
                        update = self._ui_queue.get(timeout=0.016)  # ~60 FPS
                        updates.append(update)
                    except queue.Empty:
                        break
                
                if updates:
                    # Executar updates em batch
                    app = self.app()
                    if app:
                        app.after(0, lambda: self._execute_ui_batch(updates))
                
            except Exception as e:
                logging.error(f"Error in UI worker: {e}")
                time.sleep(0.1)
    
    def _execute_ui_batch(self, updates):
        """Executa um lote de atualizações de UI."""
        try:
            for update_func, args, kwargs in updates:
                update_func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error executing UI batch: {e}")
    
    def queue_ui_update(self, update_func: Callable, *args, **kwargs):
        """Adiciona uma atualização de UI à fila para processamento otimizado."""
        self._ui_queue.put((update_func, args, kwargs))
    
    def debounce(self, delay: float = 0.3):
        """Decorator para debounce de funções."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Cancelar timer anterior se existir
                if func.__name__ in self._debounce_timers:
                    self._debounce_timers[func.__name__].cancel()
                
                # Criar novo timer
                timer = threading.Timer(delay, func, args, kwargs)
                self._debounce_timers[func.__name__] = timer
                timer.start()
            
            return wrapper
        return decorator
    
    def throttle(self, delay: float = 0.1):
        """Decorator para throttle de funções."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                current_time = time.time()
                last_call = self._throttle_timers.get(func.__name__, 0)
                
                if current_time - last_call >= delay:
                    self._throttle_timers[func.__name__] = current_time
                    return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    @lru_cache(maxsize=512)
    def cached_operation(self, operation_id: str, *args):
        """Cache para operações custosas."""
        return self._cache.get(operation_id)
    
    def async_operation(self, func: Callable, *args, **kwargs):
        """Executa operação de forma assíncrona."""
        future = self._executor.submit(func, *args, **kwargs)
        return future
    
    def _setup_memory_management(self):
        """Configura gerenciamento automático de memória."""
        def memory_monitor():
            while True:
                try:
                    time.sleep(30)  # Verificar a cada 30 segundos
                    self._check_memory_usage()
                except Exception as e:
                    logging.error(f"Error in memory monitor: {e}")
        
        thread = threading.Thread(target=memory_monitor, daemon=True, name="MemoryMonitor")
        thread.start()
    
    def _check_memory_usage(self):
        """Verifica uso de memória e otimiza se necessário."""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            if memory_mb > self.memory_threshold:
                logging.warning(f"High memory usage: {memory_mb:.1f}MB, optimizing...")
                self._optimize_memory()
            
        except ImportError:
            # psutil não disponível
            pass
        except Exception as e:
            logging.error(f"Error checking memory: {e}")
    
    def _optimize_memory(self):
        """Otimiza uso de memória."""
        # Limpar cache
        if len(self._cache) > self.max_cache_size:
            # Manter apenas os itens mais recentes
            items = list(self._cache.items())
            self._cache = dict(items[-self.max_cache_size//2:])
        
        # Forçar garbage collection
        collected = gc.collect()
        logging.debug(f"Memory optimization: freed {collected} objects")
    
    def _setup_cpu_monitoring(self):
        """Configura monitoramento de CPU."""
        def cpu_monitor():
            while True:
                try:
                    time.sleep(60)  # Verificar a cada minuto
                    self._check_cpu_usage()
                except Exception as e:
                    logging.error(f"Error in CPU monitor: {e}")
        
        thread = threading.Thread(target=cpu_monitor, daemon=True, name="CPUMonitor")
        thread.start()
    
    def _check_cpu_usage(self):
        """Verifica uso de CPU e ajusta configurações se necessário."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent > self.cpu_threshold:
                logging.warning(f"High CPU usage: {cpu_percent:.1f}%, adjusting performance settings...")
                self._adjust_performance_settings(cpu_percent)
            
        except ImportError:
            # psutil não disponível
            pass
        except Exception as e:
            logging.error(f"Error checking CPU: {e}")
    
    def _adjust_performance_settings(self, cpu_percent):
        """Ajusta configurações de performance baseado no uso de CPU."""
        if cpu_percent > 90:
            # CPU muito alta, reduzir agressivamente
            self.ui_update_interval = 0.033  # ~30 FPS
            self.max_cache_size = 500
        elif cpu_percent > 80:
            # CPU alta, reduzir moderadamente
            self.ui_update_interval = 0.025  # ~40 FPS
            self.max_cache_size = 750
    
    def optimize_network_operations(self):
        """Otimiza operações de rede."""
        # Implementar connection pooling
        # Configurar timeouts adaptativos
        # Implementar retry com backoff exponencial
        pass
    
    def optimize_file_operations(self):
        """Otimiza operações de arquivo."""
        # Implementar cache de arquivos
        # Usar operações assíncronas quando possível
        # Implementar compressão para arquivos grandes
        pass
    
    def get_performance_metrics(self):
        """Retorna métricas de performance."""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            
            return {
                "memory_usage_mb": memory_mb,
                "cpu_usage_percent": cpu_percent,
                "cache_size": len(self._cache),
                "ui_queue_size": self._ui_queue.qsize(),
                "active_threads": len(self._background_tasks),
                "ui_update_interval": self.ui_update_interval
            }
        except ImportError:
            return {"error": "psutil not available"}
        except Exception as e:
            return {"error": str(e)}
    
    def cleanup(self):
        """Limpa recursos do otimizador."""
        try:
            # Cancelar timers
            for timer in self._debounce_timers.values():
                timer.cancel()
            for timer in self._throttle_timers.values():
                timer.cancel()
            
            # Parar executor (sem timeout para compatibilidade)
            self._executor.shutdown(wait=True)
            
            # Limpar caches
            self._cache.clear()
            
            logging.debug("Advanced performance optimizer cleanup completed")
            
        except Exception as e:
            logging.error(f"Error during advanced performance optimizer cleanup: {e}")


class UIOptimizer:
    """
    Otimizador específico para interface de usuário.
    """
    
    def __init__(self, app):
        self.app = weakref.ref(app)
        self._widget_cache = {}
        self._layout_cache = {}
        self._update_queue = queue.Queue()
        
    def optimize_widget_creation(self, widget_class, *args, **kwargs):
        """Otimiza criação de widgets com cache."""
        cache_key = f"{widget_class.__name__}_{hash(str(args) + str(sorted(kwargs.items())))}"
        
        if cache_key in self._widget_cache:
            return self._widget_cache[cache_key]
        
        widget = widget_class(*args, **kwargs)
        self._widget_cache[cache_key] = widget
        return widget
    
    def batch_layout_updates(self, container, updates):
        """Aplica atualizações de layout em batch."""
        # Desabilitar redraw durante atualizações
        container.update_idletasks()
        
        for update_func in updates:
            update_func()
        
        # Reabilitar redraw
        container.update_idletasks()
    
    def optimize_scrolling(self, scrollable_widget):
        """Otimiza scrolling de widgets."""
        # Implementar virtual scrolling para listas grandes
        # Implementar lazy loading de conteúdo
        pass


class NetworkOptimizer:
    """
    Otimizador específico para operações de rede.
    """
    
    def __init__(self):
        self._connection_pool = {}
        self._dns_cache = {}
        self._timeout_cache = {}
        
    def optimize_ping_operations(self, hosts: List[str], max_concurrent: int = 10):
        """Otimiza operações de ping com pool de threads."""
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {executor.submit(self._ping_host, host): host for host in hosts}
            
            results = {}
            for future in as_completed(futures):
                host = futures[future]
                try:
                    result = future.result(timeout=2.0)
                    results[host] = result
                except Exception as e:
                    results[host] = {"error": str(e)}
            
            return results
    
    def _ping_host(self, host: str):
        """Ping otimizado para um host."""
        # Implementar ping com timeout adaptativo
        # Usar cache de DNS
        # Implementar retry com backoff
        pass
    
    def optimize_port_scanning(self, target: str, ports: List[int], max_concurrent: int = 20):
        """Otimiza escaneamento de portas."""
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {executor.submit(self._scan_port, target, port): port for port in ports}
            
            results = {}
            for future in as_completed(futures):
                port = futures[future]
                try:
                    result = future.result(timeout=1.0)
                    results[port] = result
                except Exception as e:
                    results[port] = {"error": str(e)}
            
            return results
    
    def _scan_port(self, target: str, port: int):
        """Escaneia uma porta específica."""
        # Implementar scan de porta otimizado
        # Usar timeouts adaptativos
        # Implementar cache de resultados
        pass


# Instância global do otimizador avançado
advanced_optimizer = None

def initialize_advanced_optimizer(app):
    """Inicializa o otimizador avançado."""
    global advanced_optimizer
    advanced_optimizer = AdvancedPerformanceOptimizer(app)
    return advanced_optimizer

def get_advanced_optimizer():
    """Retorna a instância do otimizador avançado."""
    return advanced_optimizer
