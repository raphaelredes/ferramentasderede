#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Benchmark de Performance
Testa e compara a performance da aplicação antes e depois das otimizações.
"""

import time
import threading
import psutil
import os
import sys
from typing import Dict, List, Any
import logging

def measure_execution_time(func):
    """Decorator para medir tempo de execução de funções."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    return wrapper

class PerformanceBenchmark:
    """Classe para executar benchmarks de performance."""
    
    def __init__(self):
        self.results = {}
        self.baseline_results = {}
        
    def measure_memory_usage(self) -> Dict[str, float]:
        """Mede uso de memória atual."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
                "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
                "percent": process.memory_percent()
            }
        except Exception as e:
            logging.error(f"Error measuring memory: {e}")
            return {"error": str(e)}
    
    def measure_cpu_usage(self, duration: float = 5.0) -> Dict[str, float]:
        """Mede uso de CPU durante um período."""
        try:
            process = psutil.Process()
            
            # Medir CPU por um período
            cpu_percent = process.cpu_percent(interval=duration)
            
            return {
                "cpu_percent": cpu_percent,
                "num_threads": process.num_threads(),
                "num_handles": getattr(process, 'num_handles', lambda: 0)()
            }
        except Exception as e:
            logging.error(f"Error measuring CPU: {e}")
            return {"error": str(e)}
    
    @measure_execution_time
    def benchmark_import_time(self) -> Dict[str, Any]:
        """Benchmark do tempo de importação de módulos."""
        import_times = {}
        
        modules_to_test = [
            "app.gui",
            "app.app_controller", 
            "app.network_tools",
            "app.performance_optimizer",
            "app.advanced_performance_optimizer"
        ]
        
        for module_name in modules_to_test:
            start_time = time.time()
            try:
                __import__(module_name)
                import_time = time.time() - start_time
                import_times[module_name] = import_time
            except Exception as e:
                import_times[module_name] = {"error": str(e)}
        
        return import_times
    
    @measure_execution_time
    def benchmark_ui_creation(self) -> Dict[str, Any]:
        """Benchmark da criação de widgets de UI."""
        try:
            import customtkinter as ctk
            
            # Criar widgets básicos
            widgets = []
            for i in range(100):
                widget = ctk.CTkLabel(text=f"Widget {i}")
                widgets.append(widget)
            
            return {"widgets_created": len(widgets)}
            
        except Exception as e:
            return {"error": str(e)}
    
    @measure_execution_time
    def benchmark_network_operations(self) -> Dict[str, Any]:
        """Benchmark de operações de rede."""
        try:
            from app.network_performance_optimizer import get_network_optimizer
            
            optimizer = get_network_optimizer()
            
            # Testar ping em lote
            test_hosts = ["127.0.0.1", "8.8.8.8", "1.1.1.1"]
            ping_results = optimizer.batch_ping_hosts(test_hosts)
            
            # Testar scan de portas
            test_ports = [80, 443, 22, 21, 25]
            scan_results = optimizer.batch_port_scan("127.0.0.1", test_ports)
            
            return {
                "ping_results": len(ping_results),
                "scan_results": len(scan_results),
                "stats": optimizer.get_performance_stats()
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    @measure_execution_time
    def benchmark_file_operations(self) -> Dict[str, Any]:
        """Benchmark de operações de arquivo."""
        try:
            # Testar leitura de arquivos de configuração
            config_files = [
                "app/config.py",
                "requirements.txt",
                "main.py"
            ]
            
            total_size = 0
            for file_path in config_files:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        total_size += len(content)
            
            return {
                "files_read": len(config_files),
                "total_size_bytes": total_size
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Executa benchmark completo da aplicação."""
        print("🚀 Iniciando benchmark completo de performance...")
        print("=" * 60)
        
        benchmark_results = {}
        
        # 1. Medir uso de memória inicial
        print("📊 Medindo uso de memória...")
        memory_before = self.measure_memory_usage()
        benchmark_results["memory_before"] = memory_before
        
        # 2. Medir uso de CPU
        print("🖥️  Medindo uso de CPU...")
        cpu_usage = self.measure_cpu_usage()
        benchmark_results["cpu_usage"] = cpu_usage
        
        # 3. Benchmark de importação
        print("📦 Testando tempo de importação...")
        import_results, import_time = self.benchmark_import_time()
        benchmark_results["import_benchmark"] = {
            "results": import_results,
            "total_time": import_time
        }
        
        # 4. Benchmark de UI
        print("🎨 Testando criação de widgets...")
        ui_results, ui_time = self.benchmark_ui_creation()
        benchmark_results["ui_benchmark"] = {
            "results": ui_results,
            "total_time": ui_time
        }
        
        # 5. Benchmark de rede
        print("🌐 Testando operações de rede...")
        network_results, network_time = self.benchmark_network_operations()
        benchmark_results["network_benchmark"] = {
            "results": network_results,
            "total_time": network_time
        }
        
        # 6. Benchmark de arquivo
        print("📁 Testando operações de arquivo...")
        file_results, file_time = self.benchmark_file_operations()
        benchmark_results["file_benchmark"] = {
            "results": file_results,
            "total_time": file_time
        }
        
        # 7. Medir uso de memória final
        print("📊 Medindo uso de memória final...")
        memory_after = self.measure_memory_usage()
        benchmark_results["memory_after"] = memory_after
        
        # Calcular diferenças
        if "rss_mb" in memory_before and "rss_mb" in memory_after:
            memory_diff = memory_after["rss_mb"] - memory_before["rss_mb"]
            benchmark_results["memory_difference_mb"] = memory_diff
        
        return benchmark_results
    
    def print_benchmark_results(self, results: Dict[str, Any]):
        """Imprime resultados do benchmark de forma organizada."""
        print("\n" + "=" * 60)
        print("📋 RESULTADOS DO BENCHMARK")
        print("=" * 60)
        
        # Memória
        if "memory_before" in results:
            print(f"💾 Memória inicial: {results['memory_before'].get('rss_mb', 0):.1f} MB")
        
        if "memory_after" in results:
            print(f"💾 Memória final: {results['memory_after'].get('rss_mb', 0):.1f} MB")
        
        if "memory_difference_mb" in results:
            diff = results["memory_difference_mb"]
            print(f"💾 Diferença de memória: {diff:+.1f} MB")
        
        # CPU
        if "cpu_usage" in results:
            cpu = results["cpu_usage"]
            print(f"🖥️  Uso de CPU: {cpu.get('cpu_percent', 0):.1f}%")
            print(f"🖥️  Threads ativas: {cpu.get('num_threads', 0)}")
        
        # Importação
        if "import_benchmark" in results:
            import_bench = results["import_benchmark"]
            print(f"📦 Tempo total de importação: {import_bench['total_time']:.3f}s")
            
            for module, time_taken in import_bench["results"].items():
                if isinstance(time_taken, (int, float)):
                    print(f"   - {module}: {time_taken:.3f}s")
        
        # UI
        if "ui_benchmark" in results:
            ui_bench = results["ui_benchmark"]
            print(f"🎨 Tempo de criação de widgets: {ui_bench['total_time']:.3f}s")
            print(f"   - Widgets criados: {ui_bench['results'].get('widgets_created', 0)}")
        
        # Rede
        if "network_benchmark" in results:
            network_bench = results["network_benchmark"]
            print(f"🌐 Tempo de operações de rede: {network_bench['total_time']:.3f}s")
            
            if "results" in network_bench["results"]:
                stats = network_bench["results"]["stats"]
                print(f"   - Cache DNS: {stats.get('dns_cache_size', 0)} entradas")
                print(f"   - Cache ping: {stats.get('ping_cache_size', 0)} entradas")
        
        # Arquivo
        if "file_benchmark" in results:
            file_bench = results["file_benchmark"]
            print(f"📁 Tempo de operações de arquivo: {file_bench['total_time']:.3f}s")
            print(f"   - Arquivos lidos: {file_bench['results'].get('files_read', 0)}")
            print(f"   - Tamanho total: {file_bench['results'].get('total_size_bytes', 0)} bytes")
        
        print("\n" + "=" * 60)
        print("✅ Benchmark concluído!")
        print("=" * 60)
    
    def save_benchmark_results(self, results: Dict[str, Any], filename: str = "benchmark_results.json"):
        """Salva resultados do benchmark em arquivo JSON."""
        try:
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"💾 Resultados salvos em: {filename}")
        except Exception as e:
            print(f"❌ Erro ao salvar resultados: {e}")


def main():
    """Função principal do benchmark."""
    print("🔧 BENCHMARK DE PERFORMANCE - FERRAMENTAS DE REDE")
    print("=" * 60)
    
    # Configurar logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Criar benchmark
    benchmark = PerformanceBenchmark()
    
    # Executar benchmark
    results = benchmark.run_comprehensive_benchmark()
    
    # Exibir resultados
    benchmark.print_benchmark_results(results)
    
    # Salvar resultados
    benchmark.save_benchmark_results(results)
    
    return results


if __name__ == "__main__":
    main()
