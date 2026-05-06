import os
from pathlib import Path
import platform

APP_VERSION = "1.2.2"

# --- Diretórios e Arquivos ---
# Definir diretório de dados do usuário (AppData/Roaming para persistência correta)
if platform.system() == "Windows":
    APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FerramentasDeRede")
else:
    APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".ferramentasderede")

# Garantir que o diretório existe
os.makedirs(APP_DATA_DIR, exist_ok=True)

# Arquivos de configuração e dados
HOSTS_FILE = os.path.join(APP_DATA_DIR, "hosts.json")
FAVORITES_FILE = os.path.join(APP_DATA_DIR, "favorites.json")
UI_PREFS_FILE = os.path.join(APP_DATA_DIR, "ui_preferences.json")
DISCOVERY_CACHE_FILE = os.path.join(APP_DATA_DIR, "discovery_cache.json")
CRED_FILE = os.path.join(APP_DATA_DIR, "credentials.enc")
SALT_FILE = os.path.join(APP_DATA_DIR, "key.salt")
VAULT_META_FILE = os.path.join(APP_DATA_DIR, "vault_meta.json")

# --- Configurações de Performance ---
MAX_CONCURRENT_HOST_CHECKS = 30  # Aumentado para melhor performance
HOST_CHECK_BATCH_SIZE = 25      # Aumentado para processar mais hosts por lote
HOST_CHECK_BATCH_DELAY = 0.03   # Reduzido para acelerar o carregamento
UI_UPDATE_BATCH_DELAY = 0.016   # ~60 FPS para atualizações mais suaves
MAX_WORKER_THREADS = 15         # Aumentado para mais paralelismo
CACHE_CLEANUP_INTERVAL = 300    # Limpeza de cache (5 minutos)
MEMORY_MONITOR_INTERVAL = 600   # Monitoramento de memória (10 minutos)

# --- Configurações Avançadas de Performance ---
ADVANCED_PERFORMANCE_ENABLED = True  # Habilitar otimizações avançadas
UI_UPDATE_INTERVAL = 0.016          # Intervalo de atualização da UI (~60 FPS)
MAX_CACHE_SIZE = 1000               # Tamanho máximo do cache
MEMORY_THRESHOLD_MB = 150           # Limite de memória para otimização
CPU_THRESHOLD_PERCENT = 80          # Limite de CPU para otimização
NETWORK_TIMEOUT_ADAPTIVE = True     # Timeouts adaptativos para rede
BATCH_UI_UPDATES = True             # Atualizações de UI em lote
DEBOUNCE_DELAY = 0.3                # Delay para debounce de funções
THROTTLE_DELAY = 0.1                # Delay para throttle de funções

# --- Configurações de Log ---
# Níveis: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"  # Mudado para INFO para reduzir overhead de logs

# --- Configurações de Rede ---
STATUS_PING_TIMEOUT = 2.0  # Timeout padrão para verificação de status (segundos)
STATUS_UPDATE_INTERVAL = 5.0  # Intervalo de atualização de status (segundos)

# Definição de portas
ALL_PORTS = range(1, 65536)

# Portas mais comuns para escaneamento rápido
TOP_60_PORTS = [
    20, 21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445, 993, 995,
    1723, 3306, 3389, 5900, 8080, 8443, 
    # Adicione mais portas conforme necessário para chegar a 60 ou as mais relevantes
    5000, 5432, 6379, 27017, 8000, 8888
]

port_number_to_name = {
    20: "FTP Data", 21: "FTP Control", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 111: "RPC", 135: "RPC Endpoint Mapper",
    139: "NetBIOS", 143: "IMAP", 443: "HTTPS", 445: "SMB", 993: "IMAPS",
    995: "POP3S", 1723: "PPTP", 3306: "MySQL", 3389: "RDP", 5900: "VNC",
    8080: "HTTP-Proxy", 8443: "HTTPS-Alt", 5000: "UPnP/Flask", 5432: "PostgreSQL",
    6379: "Redis", 27017: "MongoDB", 8000: "HTTP-Alt", 8888: "HTTP-Alt"
}