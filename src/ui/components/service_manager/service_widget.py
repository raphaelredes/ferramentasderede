# app/ui_components/service_manager/service_widget.py
# Um widget que representa uma única linha na lista de serviços.

import customtkinter

class ServiceWidget(customtkinter.CTkFrame):
    def __init__(self, master, app, service_data, action_callback):
        super().__init__(master)
        self.pack(fill="x", pady=2, padx=2)
        self.grid_columnconfigure(0, weight=1)

        self.app = app
        self.service_data = service_data
        self.action_callback = action_callback
        
        self._create_widgets()

    def _create_widgets(self):
        name = self.service_data.get("Name")
        display_name = self.service_data.get("DisplayName")
        
        status_obj = self.service_data.get("Status")
        is_running = (isinstance(status_obj, str) and status_obj == "Running") or \
                     (isinstance(status_obj, int) and status_obj == 4)
        status_str = "Running" if is_running else "Stopped"
        
        # Usar cores melhoradas para o tema claro
        current_mode = customtkinter.get_appearance_mode().lower()
        if current_mode == "light":
            status_color = "#107C10" if is_running else "#D13438"  # Cores mais suaves para tema claro
        else:
            status_color = "#2ECC71" if is_running else "#E74C3C"  # Cores originais para tema escuro
        
        info_label = customtkinter.CTkLabel(self, text=f"{display_name}\n({name})", justify="left", anchor="w")
        info_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        status_label = customtkinter.CTkLabel(self, text=status_str, text_color=status_color, font=("", 12, "bold"))
        status_label.grid(row=0, column=1, padx=10, pady=5)

        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=0, column=2, padx=10, pady=5)

        # Cores melhoradas para botões baseadas no tema
        if current_mode == "light":
            start_fg = "#107C10"
            start_hover = "#0F6E0F"
            stop_fg = "#D13438"
            stop_hover = "#B52D30"
        else:
            start_fg = "#2ECC71"
            start_hover = "#27AE60"
            stop_fg = "#E74C3C"
            stop_hover = "#C0392B"
            
        start_btn = customtkinter.CTkButton(button_frame, text="▶", width=30, command=lambda: self.action_callback(name, "start"), fg_color=start_fg, hover_color=start_hover)
        start_btn.pack(side="left", padx=2)
        
        stop_btn = customtkinter.CTkButton(button_frame, text="■", width=30, command=lambda: self.action_callback(name, "stop"), fg_color=stop_fg, hover_color=stop_hover)
        stop_btn.pack(side="left", padx=2)
        
        restart_btn = customtkinter.CTkButton(button_frame, text="⟳", width=30, command=lambda: self.action_callback(name, "restart"))
        restart_btn.pack(side="left", padx=2)
        
        # Armazenar referências para atualização de tema
        self.status_label = status_label
        self.start_btn = start_btn
        self.stop_btn = stop_btn
        self.restart_btn = restart_btn
        self.is_running = is_running
    
    def update_theme(self):
        """
        Atualiza as cores do widget quando o tema muda.
        """
        current_mode = customtkinter.get_appearance_mode().lower()
        
        # Atualizar cor do status
        if current_mode == "light":
            status_color = "#107C10" if self.is_running else "#D13438"
            start_fg = "#107C10"
            start_hover = "#0F6E0F"
            stop_fg = "#D13438"
            stop_hover = "#B52D30"
        else:
            status_color = "#2ECC71" if self.is_running else "#E74C3C"
            start_fg = "#2ECC71"
            start_hover = "#27AE60"
            stop_fg = "#E74C3C"
            stop_hover = "#C0392B"
        
        # Aplicar cores atualizadas
        if hasattr(self, 'status_label'):
            self.status_label.configure(text_color=status_color)
        if hasattr(self, 'start_btn'):
            self.start_btn.configure(fg_color=start_fg, hover_color=start_hover)
        if hasattr(self, 'stop_btn'):
            self.stop_btn.configure(fg_color=stop_fg, hover_color=stop_hover)

        if is_running:
            start_btn.configure(state="disabled")
        else: 
            stop_btn.configure(state="disabled")
            restart_btn.configure(state="disabled")