"""
Módulo Config - Configurações da Aplicação

Contém todas as configurações e constantes da aplicação:
- Configurações de rede
- Configurações de performance
- Configurações de UI
- Constantes da aplicação
"""

from .settings import *

__all__ = [
    "APP_VERSION",
    "TOP_60_PORTS",
    "ALL_PORTS",
    "common_port_mapping",
    "port_number_to_name",
    "MONOSPACE_FONT",
    "MEDIUM_FONT_SIZE",
    "UI_PREFS_FILE",
    "FAVORITES_FILE",
    "DISCOVERY_CACHE_FILE",
    "STATUS_UPDATE_INTERVAL",
    "STATUS_PING_TIMEOUT",
    "MAX_CONCURRENT_HOST_CHECKS",
    "HOST_CHECK_BATCH_SIZE",
    "HOST_CHECK_BATCH_DELAY",
    "UI_UPDATE_BATCH_DELAY",
    "MAX_WORKER_THREADS",
    "CACHE_CLEANUP_INTERVAL",
    "MEMORY_MONITOR_INTERVAL",
    "ADVANCED_PERFORMANCE_ENABLED",
    "UI_UPDATE_INTERVAL",
    "MAX_CACHE_SIZE",
    "MEMORY_THRESHOLD_MB",
    "CPU_THRESHOLD_PERCENT",
    "NETWORK_TIMEOUT_ADAPTIVE",
    "BATCH_UI_UPDATES",
    "DEBOUNCE_DELAY",
    "THROTTLE_DELAY",
    "LOG_LEVEL"
]
