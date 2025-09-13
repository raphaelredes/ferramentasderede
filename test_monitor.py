# test_monitor.py
# Teste do sistema de monitoramento

import time
import logging
from src.utils.performance_monitor import PerformanceMonitor

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_monitor():
    print("🔍 Testando Sistema de Monitoramento de Performance")
    print("=" * 60)
    
    # Criar monitor
    monitor = PerformanceMonitor()
    
    # Configurar callbacks de teste
    def on_timeout(command, duration):
        print(f"⏱️ TIMEOUT: Comando '{command}' travou por {duration:.1f}s")
    
    def on_high_resources(metrics):
        print(f"⚠️ RECURSOS: CPU: {metrics.cpu_percent:.1f}%, RAM: {metrics.memory_mb:.1f}MB")
    
    def on_freeze():
        print("🚨 FREEZE: Mainloop travado detectado!")
    
    monitor.on_command_timeout = on_timeout
    monitor.on_high_resource_usage = on_high_resources
    monitor.on_mainloop_freeze = on_freeze
    
    # Iniciar monitoramento
    monitor.start_monitoring()
    print("✅ Monitor iniciado")
    
    # Simular comando normal
    print("\n📋 Teste 1: Comando normal (5s)")
    monitor.register_command_start("test_normal")
    time.sleep(5)
    monitor.register_command_end("test_normal")
    print("✅ Comando normal finalizado")
    
    # Simular comando com timeout
    print("\n⏱️ Teste 2: Comando com timeout (35s)")
    monitor.register_command_start("test_timeout")
    print("   Aguardando timeout em 30s...")
    
    # Aguardar 35 segundos para ativar timeout
    for i in range(35):
        time.sleep(1)
        if i % 10 == 9:
            print(f"   Aguardando... {i+1}s")
    
    monitor.register_command_end("test_timeout")
    print("✅ Comando com timeout finalizado")
    
    # Verificar status
    print("\n📊 Status Final:")
    status = monitor.get_current_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # Parar monitor
    monitor.stop_monitoring()
    print("\n✅ Monitor parado")
    print("🎯 Teste concluído!")

if __name__ == "__main__":
    test_monitor()