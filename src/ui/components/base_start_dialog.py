# app/ui_components/base_start_dialog.py
# Classe base para diálogos de inicialização que DEVEM ser centralizados na tela.

from .base_dialog import BaseDialog

class BaseStartDialog(BaseDialog):
    """
    Uma classe base especial para diálogos que aparecem antes da janela principal
    ser visível. Garante que eles sejam sempre centralizados na TELA, e não
    na janela principal (que estaria oculta ou em posição imprevisível).
    """
    def __init__(self, app, title=""):
        # Para diálogos de início, não usar transient para garantir centralização independente
        super().__init__(app, title)
        # Remover a dependência transient para diálogos iniciais
        self.transient(None)