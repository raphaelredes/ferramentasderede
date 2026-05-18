"""
Módulo Network - Funcionalidades de Rede

Contém todas as funcionalidades relacionadas a rede:
- Ferramentas de rede (ping, port scan, etc.)
- Otimizadores de performance de rede
- Monitoramento de status
"""

from .tools import NetworkTools
from .optimizer import NetworkPerformanceOptimizer

__all__ = [
    "NetworkTools",
    "NetworkPerformanceOptimizer",
]
