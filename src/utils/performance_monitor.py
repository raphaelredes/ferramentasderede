# src/utils/performance_monitor.py
# Sistema de monitoramento de performance e detecção de travamentos

import time
import threading
import logging
import psutil
import gc
from collections import deque
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field

@dataclass
class PerformanceMetrics:
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    thread_count: int = 0
    mainloop_responsive: bool = True
    active_commands: int = 0
    queue_size: int = 0

class PerformanceMonitor:
    def __init__(self, app_instance=None, max_history=100):
        self.app = app_instance
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.active_commands: Dict[str, float] = {}
        self.hanging_commands: Dict[str, float] = {}
        
        # Configurações de limite
        self.COMMAND_TIMEOUT = 30.0  # 30 segundos para timeout de comando
        self.MAINLOOP_TIMEOUT = 5.0   # 5 segundos para verificar responsividade
        self.CPU_THRESHOLD = 80.0     # 80% CPU considerado alto
        self.MEMORY_THRESHOLD = 500.0 # 500MB considerado alto
        
        # Controle de monitoramento
        self.monitoring = False
        self.monitor_thread = None
        self.last_mainloop_check = time.time()
        self.mainloop_responsive = True
        
        # Callbacks para alertas
        self.on_command_timeout: Optional[Callable] = None
        self.on_high_resource_usage: Optional[Callable] = None
        self.on_mainloop_freeze: Optional[Callable] = None
        
        logging.info("PerformanceMonitor initialized")

    def start_monitoring(self):
        """Inicia o monitoramento em thread separada"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            daemon=True, 
            name="PerformanceMonitor"
        )
        self.monitor_thread.start()
        logging.info("PerformanceMonitor started")

    def stop_monitoring(self):
        """Para o monitoramento"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        logging.info("PerformanceMonitor stopped")

    def _monitor_loop(self):
        """Loop principal de monitoramento"""
        while self.monitoring:
            try:
                # Coleta métricas
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Verifica comandos em timeout
                self._check_command_timeouts()
                
                # Verifica responsividade do mainloop
                self._check_mainloop_responsiveness()
                
                # Verifica uso de recursos
                self._check_resource_usage(metrics)
                
                # Log periódico (a cada 30 segundos)
                if len(self.metrics_history) % 30 == 0:
                    self._log_performance_summary()
                
                time.sleep(1.0)  # Verifica a cada segundo
                
            except Exception as e:
                logging.error(f"Erro no monitor de performance: {e}")
                time.sleep(5.0)  # Aguarda mais tempo em caso de erro

    def _collect_metrics(self) -> PerformanceMetrics:
        """Coleta métricas de performance atual"""
        try:
            process = psutil.Process()
            
            metrics = PerformanceMetrics(
                cpu_percent=process.cpu_percent(),
                memory_mb=process.memory_info().rss / 1024 / 1024,
                thread_count=process.num_threads(),
                mainloop_responsive=self.mainloop_responsive,
                active_commands=len(self.active_commands),
                queue_size=0  # Será implementado quando integrado
            )
            
            return metrics
            
        except Exception as e:
            logging.error(f"Erro ao coletar métricas: {e}")
            return PerformanceMetrics()

    def _check_command_timeouts(self):
        """Verifica comandos que podem ter travado"""
        current_time = time.time()
        timed_out_commands = []
        
        for command, start_time in self.active_commands.items():
            duration = current_time - start_time
            
            if duration > self.COMMAND_TIMEOUT:
                timed_out_commands.append((command, duration))
                
                # Move para lista de comandos travados
                if command not in self.hanging_commands:
                    self.hanging_commands[command] = start_time
                    logging.warning(f"Comando '{command}' pode ter travado (duração: {duration:.1f}s)")
                    
                    # Callback de timeout
                    if self.on_command_timeout:
                        try:
                            self.on_command_timeout(command, duration)
                        except Exception as e:
                            logging.error(f"Erro no callback de timeout: {e}")
        
        # Remove comandos com timeout da lista ativa
        for command, _ in timed_out_commands:
            self.active_commands.pop(command, None)

    def _check_mainloop_responsiveness(self):
        """Verifica se o mainloop está responsivo"""
        if not self.app:
            return
            
        current_time = time.time()
        since_last_check = current_time - self.last_mainloop_check
        
        if since_last_check > self.MAINLOOP_TIMEOUT:
            # Testa responsividade agendando uma função simples
            self._test_mainloop_response()

    def _test_mainloop_response(self):
        """Testa a responsividade do mainloop"""
        test_start = time.time()
        response_received = threading.Event()
        
        def mainloop_test():
            response_received.set()
        
        try:
            if self.app and hasattr(self.app, 'after'):
                self.app.after(0, mainloop_test)
                
                # Aguarda resposta por até 2 segundos
                if response_received.wait(timeout=2.0):
                    response_time = time.time() - test_start
                    self.mainloop_responsive = True
                    self.last_mainloop_check = time.time()
                    
                    if response_time > 1.0:  # Resposta lenta
                        logging.warning(f"Mainloop respondendo lentamente: {response_time:.2f}s")
                else:
                    # Mainloop não respondeu
                    self.mainloop_responsive = False
                    logging.error("Mainloop não está respondendo!")
                    
                    if self.on_mainloop_freeze:
                        try:
                            self.on_mainloop_freeze()
                        except Exception as e:
                            logging.error(f"Erro no callback de freeze: {e}")
                            
        except Exception as e:
            logging.error(f"Erro ao testar mainloop: {e}")
            self.mainloop_responsive = False

    def _check_resource_usage(self, metrics: PerformanceMetrics):
        """Verifica uso excessivo de recursos"""
        high_usage = False
        
        # Aumentar limites para ser mais realista
        if metrics.cpu_percent > 90:  # 90% CPU (era 80%)
            logging.warning(f"Alto uso de CPU: {metrics.cpu_percent:.1f}%")
            high_usage = True
            
        if metrics.memory_mb > 1000:  # 1GB memória (era 500MB)
            logging.warning(f"Alto uso de memória: {metrics.memory_mb:.1f}MB")
            high_usage = True
            
        # Remover completamente o aviso de threads - 21 threads é normal
        # if metrics.thread_count > 20:
        #     logging.warning(f"Muitas threads ativas: {metrics.thread_count}")
        #     high_usage = True
            
        if high_usage and self.on_high_resource_usage:
            try:
                self.on_high_resource_usage(metrics)
            except Exception as e:
                logging.error(f"Erro no callback de recursos: {e}")

    def _log_performance_summary(self):
        """Log resumo de performance"""
        if not self.metrics_history:
            return
            
        recent_metrics = list(self.metrics_history)[-10:]  # Últimos 10 pontos
        
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_mb for m in recent_metrics) / len(recent_metrics)
        avg_threads = sum(m.thread_count for m in recent_metrics) / len(recent_metrics)
        
        logging.info(
            f"Performance Summary - CPU: {avg_cpu:.1f}%, "
            f"Memory: {avg_memory:.1f}MB, Threads: {avg_threads:.1f}, "
            f"Active Commands: {len(self.active_commands)}, "
            f"Hanging Commands: {len(self.hanging_commands)}"
        )

    # Métodos públicos para integração
    
    def register_command_start(self, command_name: str):
        """Registra início de um comando"""
        self.active_commands[command_name] = time.time()
        logging.debug(f"Command started: {command_name}")

    def register_command_end(self, command_name: str):
        """Registra fim de um comando"""
        if command_name in self.active_commands:
            duration = time.time() - self.active_commands[command_name]
            logging.debug(f"Command completed: {command_name} (duration: {duration:.2f}s)")
            self.active_commands.pop(command_name, None)
            
        # Remove de comandos travados se estava lá
        self.hanging_commands.pop(command_name, None)

    def force_cleanup_hanging_commands(self):
        """Força limpeza de comandos travados"""
        if self.hanging_commands:
            logging.warning(f"Forçando limpeza de {len(self.hanging_commands)} comandos travados")
            
            for command in list(self.hanging_commands.keys()):
                self.register_command_end(command)
                
            # Força garbage collection
            gc.collect()

    def get_current_status(self) -> Dict[str, Any]:
        """Retorna status atual do sistema"""
        latest_metrics = self.metrics_history[-1] if self.metrics_history else PerformanceMetrics()
        
        return {
            "monitoring": self.monitoring,
            "mainloop_responsive": self.mainloop_responsive,
            "active_commands": len(self.active_commands),
            "hanging_commands": len(self.hanging_commands),
            "cpu_percent": latest_metrics.cpu_percent,
            "memory_mb": latest_metrics.memory_mb,
            "thread_count": latest_metrics.thread_count,
            "commands_list": list(self.active_commands.keys()),
            "hanging_list": list(self.hanging_commands.keys())
        }

    def emergency_reset(self):
        """Reset de emergência para casos críticos"""
        logging.warning("Executando reset de emergência do monitor de performance")
        
        # Limpa todas as listas
        self.active_commands.clear()
        self.hanging_commands.clear()
        
        # Força garbage collection agressivo
        gc.collect()
        
        # Reseta estado
        self.mainloop_responsive = True
        self.last_mainloop_check = time.time()
        
        logging.info("Reset de emergência concluído")