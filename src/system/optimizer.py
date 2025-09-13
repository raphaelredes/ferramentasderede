# app/performance_optimizer.py
# Módulo de otimização de performance para a aplicação.

import logging
import threading
import time
import weakref
import gc
from functools import lru_cache
from typing import Dict, Any, Optional

class PerformanceOptimizer:
    """
    Classe responsável por otimizações de performance da aplicação.
    """
    
    def __init__(self, app):
        self.app = weakref.ref(app)  # Usar weak reference para evitar vazamentos
        self._cache_cleanup_timer = None
        self._memory_monitor_timer = None
        
        # Cache para tradução (evitar reprocessamento)
        self._translation_cache = {}
        
        # Cache para ícones carregados
        self._icon_cache = {}
        
        # Pool de threads reutilizáveis
        self._thread_pool = []
        self._max_threads = 5
        
    def optimize_startup(self):
        """
        Aplica otimizações durante a inicialização.
        """
        logging.debug("Applying startup optimizations")
        
        # Configurar limpeza automática de cache
        self._schedule_cache_cleanup()
        
        # Configurar monitoramento de memória
        self._schedule_memory_monitoring()
        
        # Pré-carregar recursos críticos
        self._preload_critical_resources()
    
    def optimize_imports(self):
        """
        Otimiza imports lazy para reduzir tempo de inicialização.
        """
        # Esta função pode ser chamada para imports sob demanda
        pass
    
    def _preload_critical_resources(self):
        """
        Pré-carrega recursos que serão usados frequentemente.
        """
        app = self.app()
        if not app:
            return
            
        try:
            # Verificar se o translator está disponível antes de pré-carregar
            if hasattr(app, 'translator') and app.translator:
                # Pré-carregar traduções mais usadas
                critical_translations = [
                    "label_confirm", "label_cancel", "label_error", 
                    "label_information", "ping_title", "traceroute_title"
                ]
                
                for key in critical_translations:
                    if key not in self._translation_cache:
                        self._translation_cache[key] = app.translate(key)
                
                logging.debug(f"Preloaded {len(critical_translations)} critical translations")
            else:
                logging.debug("Translator not ready yet, skipping critical resource preloading")
            
        except Exception as e:
            logging.warning(f"Error preloading critical resources: {e}")
    
    def optimize_ui_updates(self):
        """
        Otimiza atualizações da UI para melhor responsividade.
        """
        app = self.app()
        if not app:
            return
            
        # Configurar batch updates para UI
        self._setup_batch_ui_updates()
    
    def _setup_batch_ui_updates(self):
        """
        Configura sistema de batch updates para UI.
        """
        self._pending_ui_updates = []
        self._ui_update_timer = None
        
    def batch_ui_update(self, update_func, *args, **kwargs):
        """
        Adiciona uma atualização UI ao batch para execução otimizada.
        """
        self._pending_ui_updates.append((update_func, args, kwargs))
        
        # Cancelar timer anterior se existir
        if self._ui_update_timer:
            self._ui_update_timer.cancel()
        
        # Agendar execução do batch em 50ms
        self._ui_update_timer = threading.Timer(0.05, self._execute_ui_batch)
        self._ui_update_timer.start()
    
    def _execute_ui_batch(self):
        """
        Executa todas as atualizações UI pendentes em lote.
        """
        app = self.app()
        if not app or not self._pending_ui_updates:
            return
        
        def execute_updates():
            try:
                for update_func, args, kwargs in self._pending_ui_updates:
                    update_func(*args, **kwargs)
                self._pending_ui_updates.clear()
            except Exception as e:
                logging.error(f"Error executing UI batch updates: {e}")
        
        app.after(0, execute_updates)
    
    def optimize_thread_usage(self):
        """
        Otimiza uso de threads para melhor performance.
        """
        # Limitar número de threads simultâneas
        self._cleanup_finished_threads()
    
    def _cleanup_finished_threads(self):
        """
        Remove threads finalizadas do pool.
        """
        self._thread_pool = [t for t in self._thread_pool if t.is_alive()]
    
    def create_optimized_thread(self, target, *args, **kwargs):
        """
        Cria thread otimizada com pool management.
        """
        # Limpar threads mortas
        self._cleanup_finished_threads()
        
        # Se há muitas threads ativas, aguardar
        if len(self._thread_pool) >= self._max_threads:
            # Aguardar que alguma termine
            oldest_thread = self._thread_pool[0]
            oldest_thread.join(timeout=1.0)  # Aguardar máximo 1 segundo
            self._cleanup_finished_threads()
        
        # Criar nova thread
        thread = threading.Thread(target=target, daemon=True, *args, **kwargs)
        self._thread_pool.append(thread)
        thread.start()
        return thread
    
    def optimize_memory_usage(self):
        """
        Otimiza uso de memória da aplicação.
        """
        # Limpar caches antigos
        self._cleanup_old_caches()
        
        # Forçar garbage collection
        collected = gc.collect()
        logging.debug(f"Garbage collection freed {collected} objects")
        
        # Limpar referências fracas mortas
        self._cleanup_weak_references()
    
    def _cleanup_old_caches(self):
        """
        Limpa caches antigos para liberar memória.
        """
        # Limitar tamanho do cache de traduções
        if len(self._translation_cache) > 100:
            # Manter apenas as 50 mais recentes
            items = list(self._translation_cache.items())
            self._translation_cache = dict(items[-50:])
            logging.debug("Cleaned translation cache")
        
        # Limpar cache de ícones se muito grande
        if len(self._icon_cache) > 20:
            # Manter apenas os 10 mais recentes
            items = list(self._icon_cache.items())
            self._icon_cache = dict(items[-10:])
            logging.debug("Cleaned icon cache")
    
    def _cleanup_weak_references(self):
        """
        Limpa referências fracas que não são mais válidas.
        """
        # Esta implementação pode ser expandida conforme necessário
        pass
    
    def _schedule_cache_cleanup(self):
        """
        Agenda limpeza automática de cache.
        """
        def cleanup_worker():
            while True:
                try:
                    time.sleep(300)  # 5 minutos
                    self.optimize_memory_usage()
                except Exception as e:
                    logging.error(f"Error in cache cleanup worker: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True, name="CacheCleanup")
        cleanup_thread.start()
    
    def _schedule_memory_monitoring(self):
        """
        Agenda monitoramento de memória.
        """
        def memory_monitor():
            while True:
                try:
                    time.sleep(600)  # 10 minutos
                    
                    # Logs de debug sobre uso de memória
                    import psutil
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    
                    if memory_mb > 200:  # Se usar mais que 200MB
                        logging.warning(f"High memory usage: {memory_mb:.1f}MB")
                        self.optimize_memory_usage()
                    else:
                        logging.debug(f"Memory usage: {memory_mb:.1f}MB")
                        
                except ImportError:
                    # psutil não disponível, usar método alternativo
                    logging.debug("psutil not available for memory monitoring")
                    break
                except Exception as e:
                    logging.error(f"Error in memory monitor: {e}")
        
        monitor_thread = threading.Thread(target=memory_monitor, daemon=True, name="MemoryMonitor")
        monitor_thread.start()
    
    @lru_cache(maxsize=128)
    def get_cached_translation(self, key):
        """
        Obtém tradução com cache para evitar reprocessamento.
        """
        app = self.app()
        if not app:
            return key
        
        return app.translator.translate(key)
    
    def optimize_host_loading(self):
        """
        Otimiza carregamento de hosts para ser mais eficiente.
        """
        app = self.app()
        if not app:
            return
        
        # Implementar carregamento incremental de hosts
        # em vez de carregar todos de uma vez
        self._implement_incremental_host_loading()
    
    def _implement_incremental_host_loading(self):
        """
        Implementa carregamento incremental de hosts.
        """
        # Esta função pode ser expandida para carregar hosts em lotes
        # em vez de todos simultaneamente
        pass
    
    def optimize_network_operations(self):
        """
        Otimiza operações de rede para melhor performance.
        """
        # Implementar pool de conexões
        # Configurar timeouts otimizados
        # Implementar retry com backoff exponencial
        pass
    
    def get_performance_stats(self):
        """
        Retorna estatísticas de performance para debug.
        """
        return {
            "translation_cache_size": len(self._translation_cache),
            "icon_cache_size": len(self._icon_cache),
            "active_threads": len([t for t in self._thread_pool if t.is_alive()]),
            "pending_ui_updates": len(getattr(self, '_pending_ui_updates', [])),
        }
    
    def cleanup(self):
        """
        Limpa recursos quando a aplicação é fechada.
        """
        try:
            # Cancelar timers (verificar se existe primeiro)
            if hasattr(self, '_ui_update_timer') and self._ui_update_timer:
                self._ui_update_timer.cancel()
            
            # Limpar caches
            self._translation_cache.clear()
            self._icon_cache.clear()
            
            # Aguardar threads finalizarem (com timeout)
            for thread in self._thread_pool:
                if thread.is_alive():
                    thread.join(timeout=2.0)
            
            logging.debug("Performance optimizer cleanup completed")
            
        except Exception as e:
            logging.error(f"Error during performance optimizer cleanup: {e}")


class LazyImportManager:
    """
    Gerenciador de imports lazy para reduzir tempo de inicialização.
    """
    
    def __init__(self):
        self._imported_modules = {}
    
    def lazy_import(self, module_name, reload_if_exists=False):
        """
        Importa módulo apenas quando necessário.
        """
        if module_name in self._imported_modules and not reload_if_exists:
            return self._imported_modules[module_name]
        
        try:
            module = __import__(module_name, fromlist=[''])
            self._imported_modules[module_name] = module
            return module
        except ImportError as e:
            logging.error(f"Failed to lazy import {module_name}: {e}")
            return None
    
    def preload_critical_modules(self):
        """
        Pré-carrega módulos críticos em background.
        """
        critical_modules = [
            'threading', 'logging', 'json', 'os', 'time',
            'customtkinter', 'tkinter'
        ]
        
        def preload_worker():
            for module_name in critical_modules:
                try:
                    self.lazy_import(module_name)
                    time.sleep(0.01)  # Pequena pausa para não sobrecarregar
                except Exception as e:
                    logging.debug(f"Error preloading {module_name}: {e}")
        
        thread = threading.Thread(target=preload_worker, daemon=True, name="ModulePreloader")
        thread.start()


# Instância global do gerenciador de imports lazy
lazy_import_manager = LazyImportManager()
