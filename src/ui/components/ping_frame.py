# app/ui_components/ping_frame.py

import customtkinter
try:
    from ...config.settings import MONOSPACE_FONT
except ImportError:
    # Fallback para execução direta
    from src.config.settings import MONOSPACE_FONT
import logging
from .context_menu import TerminalContextMenu

class PingFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host, tool_controller):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.host = host
        logging.info(f"Initializing PingFrame for host: {self.host.get('name', self.host.get('ip', 'N/A'))}")
        self.tool_controller = tool_controller
        self._is_validating_size = False

        # Registrar callback para receber notificações de mudança de estado
        self.tool_controller.set_state_change_callback(self.update_command_status)

        # Configurar grid para melhor distribuição do espaço
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # A área de texto deve expandir

        # Configurar widget de status de comando
        status_widget = self.tool_controller.setup_command_status_widget(self)
        if status_widget:
            status_widget.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

        # Frame de controles - mais compacto
        controls_frame = customtkinter.CTkFrame(self)
        controls_frame.grid(row=1, column=0, padx=10, pady=(5, 5), sticky="ew")
        controls_frame.grid_columnconfigure(1, weight=1)

        # Primeira linha: Tamanho do pacote e botão ping
        self.packet_size_label = customtkinter.CTkLabel(controls_frame, text="")
        self.packet_size_label.grid(row=0, column=0, padx=(10, 5), pady=5)
        self.packet_size_entry = customtkinter.CTkEntry(controls_frame, placeholder_text="32", width=80)
        self.packet_size_entry.bind("<KeyRelease>", self.validate_and_correct_packet_size)
        self.packet_size_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        self.ping_button = customtkinter.CTkButton(controls_frame, text="", command=self.toggle_ping, width=100)
        self.ping_button.grid(row=0, column=2, padx=(5, 10), pady=5)

        # Segunda linha: Portas e botão teste
        self.port_label = customtkinter.CTkLabel(controls_frame, text="")
        self.port_label.grid(row=1, column=0, padx=(10, 5), pady=5)
        
        self.port_entry = customtkinter.CTkEntry(controls_frame, placeholder_text=self.app.translate("ping_ports_placeholder"))
        self.port_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        self.port_test_button = customtkinter.CTkButton(controls_frame, text="", command=self.test_ports, width=100)
        self.port_test_button.grid(row=1, column=2, padx=(5, 10), pady=5)

        # Botão de scan - mais compacto
        self.scan_button = customtkinter.CTkButton(self, text="", command=self.toggle_port_scan, height=32)
        self.scan_button.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew")

        # Área de texto - maior e mais responsiva
        self.output_textbox = customtkinter.CTkTextbox(self, wrap="word", font=MONOSPACE_FONT, height=300)
        self.output_textbox.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.output_textbox.configure(state="disabled")

        TerminalContextMenu(self.app, self.output_textbox)
        
        self.update_language()

    def validate_and_correct_packet_size(self, event=None):
        if self._is_validating_size:
            return

        self._is_validating_size = True
        try:
            entry = self.packet_size_entry
            current_text = entry.get()
            
            logging.debug(f"Validating packet size: {current_text}")
            sanitized_text = "".join(filter(str.isdigit, current_text))
            
            if sanitized_text:
                value = int(sanitized_text)
                if value > 65500:
                    logging.warning(f"Packet size {value} exceeds maximum, capping at 65500.")
                    sanitized_text = "65500"
            
            if sanitized_text != current_text:
                logging.debug(f"Correcting packet size from '{current_text}' to '{sanitized_text}'")
                cursor_pos = entry.index(customtkinter.INSERT)
                entry.delete(0, "end")
                entry.insert(0, sanitized_text)
                entry.icursor(min(cursor_pos, len(sanitized_text)))
        finally:
            self._is_validating_size = False

    def toggle_ping(self):
        running_cmd = getattr(self.tool_controller, 'running_command', None)
        is_running = getattr(self.tool_controller, 'is_running', False)
        
        logging.info(f"PingFrame.toggle_ping chamado:")
        logging.info(f"  - running_cmd: {running_cmd}")
        logging.info(f"  - is_running: {is_running}")
        
        if running_cmd == "ping" or (running_cmd and 'ping_' in running_cmd):
            self.tool_controller.stop_command()
            logging.info("Parando comando ping")
        else:
            packet_size = self.packet_size_entry.get()
            logging.info(f"Iniciando comando ping para {self.host.get('name', self.host.get('ip', 'N/A'))} com packet size: {packet_size}")
            # Usar o fluxo do controller, que já usa o IP do host de destino
            self.tool_controller.start_ping(packet_size, self.output_textbox, self.packet_size_entry)
        
        # O callback update_command_status será chamado automaticamente pelo controller
        # Mas vamos forçar uma atualização imediata para feedback visual
        self.update_button_state()

    def test_ports(self):
        # Transformar em toggle para rótulo dinâmico
        if self.tool_controller.running_command == "test_ports":
            self.tool_controller.stop_command()
            self.port_test_button.configure(text=self.app.translate("ping_scan_test"))
            return
        if self.tool_controller.is_running:
            self.app.show_info(self.app.translate("info_other_command_running"))
            logging.warning("Attempted to test ports while another command is running.")
            return
        ports = self.port_entry.get()
        logging.info(f"Testing ports {ports} on {self.host.get('name', self.host.get('ip', 'N/A'))}.")
        # Atualiza rótulo imediatamente e estado do botão
        self.port_test_button.configure(text=self.app.translate("label_cancel"), state="normal")
        # Inicia o teste
        self.tool_controller.test_ports(ports, self.output_textbox, self.port_entry)
        # Programar atualização periódica do rótulo enquanto o comando estiver em execução
        try:
            def _monitor_test_button():
                if not self.winfo_exists():
                    return
                is_running = getattr(self.tool_controller, 'is_running', False)
                running_cmd = getattr(self.tool_controller, 'running_command', None)
                if is_running and running_cmd == 'test_ports':
                    # Manter texto como cancelar
                    self.port_test_button.configure(text=self.app.translate("label_cancel"))
                    self.after(300, _monitor_test_button)
                else:
                    # Comando finalizado: restaurar texto
                    self.port_test_button.configure(text=self.app.translate("ping_scan_test"))
            self.after(300, _monitor_test_button)
        except Exception:
            # Falha silenciosa no monitor - ainda assim estados serão atualizados pelo callback central
            pass
        # Sincroniza estados
        self.update_button_state()

    def update_command_status(self, status_data):
        """Callback chamado quando o estado de um comando muda"""
        is_running = status_data.get('running', False)
        command_name = status_data.get('command', None)
        
        logging.info(f"PingFrame.update_command_status chamado:")
        logging.info(f"  - status_data: {status_data}")
        logging.info(f"  - is_running: {is_running}")
        logging.info(f"  - command_name: {command_name}")
        
        # Atualizar estado dos botões baseado no comando em execução
        self.update_button_state()

    def toggle_port_scan(self):
        running_cmd = getattr(self.tool_controller, 'running_command', None)
        
        if running_cmd == "scan" or (running_cmd and 'scan' in running_cmd):
            self.tool_controller.stop_command()
            logging.info("Stopping port scan command.")
        else:
            # Usar escaneamento de todas as portas em vez de apenas portas comuns
            self.tool_controller.start_all_ports_scan(self.output_textbox)
        
        # O callback será chamado automaticamente
        self.update_button_state()

    def update_button_state(self):
        """Atualiza o estado e texto de todos os botões baseado no comando atual"""
        try:
            is_running = getattr(self.tool_controller, 'is_running', False)
            running_cmd = getattr(self.tool_controller, 'running_command', None)

            logging.debug(f"Updating button states. Running command: {running_cmd}, Is Running: {is_running}")
            
            # Botão Ping - mais específico na detecção
            if running_cmd == 'ping' or (running_cmd and 'ping_' in running_cmd):
                self.ping_button.configure(
                    text=self.app.translate("ping_scan_stop"),
                    state="normal"
                )
                logging.debug("Botão ping configurado para PARAR")
            else:
                self.ping_button.configure(
                    text=self.app.translate("ping_scan_start"), 
                    state="disabled" if is_running else "normal"
                )
                # Cor padrão será aplicada automaticamente
                logging.debug("Botão ping configurado para INICIAR")

            # Botão de Scan de Portas
            if running_cmd == 'scan' or (running_cmd and 'scan' in running_cmd):
                self.scan_button.configure(
                    text=self.app.translate("ping_scan_ports_stop"),
                    state="normal"
                )
            else:
                self.scan_button.configure(
                    text=self.app.translate("ping_scan_ports_common"), 
                    state="disabled" if is_running else "normal"
                )
                # Cor padrão será aplicada automaticamente

            # Botão Testar Portas
            if running_cmd == 'test_ports':
                self.port_test_button.configure(
                    text=self.app.translate("label_cancel"),
                    state="normal"
                )
            else:
                self.port_test_button.configure(
                    text=self.app.translate("ping_scan_test"), 
                    state="disabled" if is_running else "normal"
                )
                # Cor padrão será aplicada automaticamente
                
        except Exception as e:
            logging.error(f"Erro ao atualizar estado dos botões: {e}")

    def update_language(self):
        logging.debug("Updating PingFrame language.")
        self.packet_size_label.configure(text=self.app.translate("ping_size"))
        self.port_label.configure(text=self.app.translate("ping_scan_ports_test"))
        self.port_test_button.configure(text=self.app.translate("ping_scan_test"))
        self.update_button_state()