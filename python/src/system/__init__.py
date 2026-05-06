"""
Módulo System - Ferramentas de Sistema

Contém funcionalidades relacionadas ao sistema:
- Ferramentas de sistema (processos, serviços, etc.)
- Otimizadores de performance do sistema
- Monitoramento de recursos
"""

from .tools import SystemTools
from .optimizer import PerformanceOptimizer

# AdvancedPerformanceOptimizer pulls in customtkinter which is a 30MB+ Tk-based
# UI dep we no longer ship in the portable build (the GUI is React via webview).
# Lazy-load it so legacy callers still work, but `import src.system` doesn't
# blow up at startup when customtkinter is absent.
def __getattr__(name):
    if name == "AdvancedPerformanceOptimizer":
        from .advanced_optimizer import AdvancedPerformanceOptimizer  # noqa: WPS433
        return AdvancedPerformanceOptimizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SystemTools",
    "PerformanceOptimizer",
    "AdvancedPerformanceOptimizer",
]
