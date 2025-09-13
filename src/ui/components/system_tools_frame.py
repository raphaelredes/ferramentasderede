# app/ui_components/system_tools_frame.py

import customtkinter
try:
    from ...config.settings import MONOSPACE_FONT
except ImportError:
    from src.config.settings import MONOSPACE_FONT
import logging
from .context_menu import TerminalContextMenu
from .system_info_panel import SystemInfoPanel 

class SystemToolsFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host, tool_controller, info_display):
        super().__init__(master, fg_color="transparent")
        self.app = app
        logging.info(f"Initializing SystemToolsFrame for host: {host.get('name', host.get('ip', 'N/A'))}")
        self.host = host
        self.tool_controller = tool_controller
        self.info_display = info_display

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=350)
        self.grid_rowconfigure(0, weight=1)

        left_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        controls_frame = customtkinter.CTkFrame(left_frame)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        controls_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.restart_button = customtkinter.CTkButton(controls_frame, text="", command=self.restart_host)
        self.restart_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.shutdown_button = customtkinter.CTkButton(controls_frame, text="", command=self.shutdown_host)
        self.shutdown_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.sysinfo_button = customtkinter.CTkButton(controls_frame, text="", command=self.get_sysinfo)
        self.sysinfo_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        schedule_frame = customtkinter.CTkFrame(controls_frame)
        schedule_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        schedule_frame.grid_columnconfigure(0, weight=1)
        self.countdown_label = customtkinter.CTkLabel(schedule_frame, text="")
        self.countdown_label.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.cancel_schedule_button = customtkinter.CTkButton(schedule_frame, text="", command=self.cancel_schedule)
        self.cancel_schedule_button.grid(row=0, column=1, padx=5, pady=5)
        
        self.output_textbox = customtkinter.CTkTextbox(left_frame, wrap="word", font=MONOSPACE_FONT, height=300)
        self.output_textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.output_textbox.configure(state="disabled")

        TerminalContextMenu(self.app, self.output_textbox)

        right_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self.info_title_label = customtkinter.CTkLabel(right_frame, text="", font=customtkinter.CTkFont(size=16, weight="bold"))
        self.info_title_label.grid(row=0, column=0, padx=10, pady=(0, 5), sticky="ew")
        
        self.system_info_panel = SystemInfoPanel(right_frame, self.app)
        self.system_info_panel.grid(row=1, column=0, sticky="nsew")
        
        # Passa as referências dos widgets da UI para o controlador
        self.tool_controller.system_info_panel = self.system_info_panel
        self.tool_controller.info_display_widget = self.info_display
        
        self.update_language()
        self.system_info_panel.display_info({})

    def restart_host(self):
        logging.info(f"Restarting host: {self.host.get('name', self.host.get('ip', 'N/A'))}")
        self.tool_controller.restart_host(self.output_textbox, self.countdown_label)

    def shutdown_host(self):
        logging.info(f"Shutting down host: {self.host.get('name', self.host.get('ip', 'N/A'))}")
        self.tool_controller.shutdown_host(self.output_textbox, self.countdown_label)

    def get_sysinfo(self):
        logging.info(f"Getting system info for host: {self.host.get('name', self.host.get('ip', 'N/A'))}")
        self.system_info_panel.display_info(None) 
        self.tool_controller.get_sysinfo()

    def cancel_schedule(self):
        self.tool_controller.cancel_shutdown(self.output_textbox, self.countdown_label)

        logging.info(f"Canceling scheduled shutdown/restart for host: {self.host.get('name', self.host.get('ip', 'N/A'))}")
    def update_language(self):
        self.restart_button.configure(text=self.app.translate("sysinfo_restart_host"))
        self.shutdown_button.configure(text=self.app.translate("sysinfo_shutdown_host"))
        self.sysinfo_button.configure(text=self.app.translate("sysinfo_get_info"))
        self.cancel_schedule_button.configure(text=self.app.translate("schedule_cancel"))
        self.countdown_label.configure(text=self.app.translate("schedule_no_active"))
        self.info_title_label.configure(text=self.app.translate("sysinfo_title_panel"))
        
        logging.debug(f"Updating language in SystemToolsFrame for host: {self.host.get('name', self.host.get('ip', 'N/A'))}")
        if self.system_info_panel:
            self.system_info_panel.update_language()