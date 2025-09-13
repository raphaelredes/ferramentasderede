import customtkinter
import logging

class EnhancedTooltip:
    """Classe para criar tooltips melhorados e interativos."""
    
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip = None
        self.timer_id = None
        
        # Bind events
        self.widget.bind("<Enter>", self._show_tooltip)
        self.widget.bind("<Leave>", self._hide_tooltip)
        
    def _show_tooltip(self, event):
        """Mostra o tooltip após o delay especificado."""
        if self.timer_id:
            self.widget.after_cancel(self.timer_id)
        
        self.timer_id = self.widget.after(self.delay, lambda: self._create_tooltip(event))
        
    def _hide_tooltip(self, event):
        """Esconde o tooltip."""
        if self.timer_id:
            self.widget.after_cancel(self.timer_id)
            self.timer_id = None
        
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
            
    def _create_tooltip(self, event):
        """Cria e exibe o tooltip."""
        try:
            # Destruir tooltip existente se houver
            if self.tooltip:
                self.tooltip.destroy()
                
            # Criar nova janela de tooltip
            self.tooltip = customtkinter.CTkToplevel()
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            # Configurar o tooltip para ficar sempre no topo
            self.tooltip.attributes('-topmost', True)
            
            # Criar label com o texto
            label = customtkinter.CTkLabel(
                self.tooltip, 
                text=self.text, 
                fg_color=("gray70", "gray30"),
                text_color=("black", "white"),
                corner_radius=6, 
                padx=8, 
                pady=4
            )
            label.pack()
            
            # Bind para esconder o tooltip quando o mouse sair
            self.tooltip.bind("<Leave>", self._hide_tooltip)
            
            # Armazenar referência no widget para limpeza
            self.widget.tooltip = self.tooltip
            
        except Exception as e:
            logging.error(f"Erro ao criar tooltip: {e}")
            
    def update_text(self, new_text):
        """Atualiza o texto do tooltip."""
        self.text = new_text
        if self.tooltip:
            # Atualizar o label existente se o tooltip estiver visível
            for child in self.tooltip.winfo_children():
                if isinstance(child, customtkinter.CTkLabel):
                    child.configure(text=new_text)
                    
    def destroy(self):
        """Destrói o tooltip e remove os binds."""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
            
        if self.timer_id:
            self.widget.after_cancel(self.timer_id)
            self.timer_id = None
            
        # Remover binds
        self.widget.unbind("<Enter>")
        self.widget.unbind("<Leave>")


def create_tooltip(widget, text, delay=500):
    """
    Função de conveniência para criar um tooltip.
    
    Args:
        widget: O widget que receberá o tooltip
        text: Texto a ser exibido no tooltip
        delay: Delay em milissegundos antes de mostrar o tooltip
        
    Returns:
        EnhancedTooltip: Instância do tooltip criado
    """
    return EnhancedTooltip(widget, text, delay)


def create_simple_tooltip(widget, text):
    """
    Cria um tooltip simples sem delay.
    
    Args:
        widget: O widget que receberá o tooltip
        text: Texto a ser exibido no tooltip
        
    Returns:
        EnhancedTooltip: Instância do tooltip criado
    """
    return EnhancedTooltip(widget, text, delay=0)

