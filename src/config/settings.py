# app/config.py
# Este arquivo armazena as configurações e constantes da aplicação.

# --- Versão da Aplicação ---
APP_VERSION = "1.1.0"

# --- Portas ---
TOP_60_PORTS = [
    20, 21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 
    1433, 1723, 3306, 3389, 5900, 8080
]

# Todas as portas TCP (1-65535)
ALL_PORTS = list(range(1, 65536))

common_port_mapping = {
    "RDP (3389)": 3389, "TeamViewer (5938)": 5938, "HTTP (80)": 80,
    "HTTPS (443)": 443, "FTP (21)": 21, "SSH (22)": 22,
    "Telnet (23)": 23, "SMTP (25)": 25, "DNS (53)": 53,
    "SMB (445)": 445, "POP3 (110)": 110, "IMAP (143)": 143
}
port_number_to_name = {v: k for k, v in common_port_mapping.items()}

# --- Fontes ---
MONOSPACE_FONT = ('Consolas', 12)
MEDIUM_FONT_SIZE = 13

# --- Arquivos de Configuração ---
UI_PREFS_FILE = "ui_preferences.json"
FAVORITES_FILE = "hosts.json"
DISCOVERY_CACHE_FILE = "discovery_cache.json"

# --- Configurações de Rede ---
STATUS_UPDATE_INTERVAL = 60  # Segundos
STATUS_PING_TIMEOUT = 1  # Segundos

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