# src/ferramentasderede/ui/components/tab_settings_dialog.py
# Janela para configurar o intervalo e renomear as abas, com suporte a drag-and-drop.

import customtkinter
from .base_dialog import BaseDialog
import logging

class TabSettingsDialog(BaseDialog):
    def __init__(self, master, app, current_interval, all_hosts, ask_initial_info):
        super().__init__(app=app, title=app.translate("tab_settings_title"))
        logging.info(f"Initializing TabSettingsDialog with interval: {current_interval}, ask_initial_info: {ask_initial_info}")
        self.hosts_local_list = list(all_hosts) 
        self.result_data = None

        self.host_frames = []
        self.drag_widget = None
        self.drag_start_y = 0
        self.drop_indicator = None

        # Definir tamanho mínimo adequado para o conteúdo
        self.minsize(500, 650)
        self.bind("<Escape>", self.on_close)

        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(4, weight=1)

        self.interval_label = customtkinter.CTkLabel(main_frame, text=self.app.translate("tab_settings_interval_label"))
        self.interval_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.interval_entry = customtkinter.CTkEntry(main_frame)
        self.interval_entry.insert(0, str(current_interval))
        self.interval_entry.grid(row=1, column=0, sticky="ew", pady=(0, 15))

        checkbox_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        checkbox_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        checkbox_frame.grid_columnconfigure(1, weight=1)

        self.ask_info_checkbox = customtkinter.CTkCheckBox(checkbox_frame, text="")
        self.ask_info_checkbox.grid(row=0, column=0, sticky="n")

        ask_info_label = customtkinter.CTkLabel(
            checkbox_frame,
            text=self.app.translate("tab_settings_ask_initial_info_label"),
            wraplength=450,
            justify="left",
            anchor="w"
        )
        ask_info_label.grid(row=0, column=1, sticky="ew")
        ask_info_label.bind("<Button-1>", lambda e: self.ask_info_checkbox.toggle())
        
        if ask_initial_info:
            self.ask_info_checkbox.select()

        self.rename_label = customtkinter.CTkLabel(main_frame, text=self.app.translate("tab_settings_rename_reorder_label"))
        self.rename_label.grid(row=3, column=0, sticky="w", pady=(0, 5))
        
        self.scrollable_frame = customtkinter.CTkScrollableFrame(main_frame)
        self.scrollable_frame.grid(row=4, column=0, sticky="nsew") 
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.drop_indicator = customtkinter.CTkFrame(self.scrollable_frame, height=2, fg_color="cyan")

        self.populate_host_list()

        bottom_buttons_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        bottom_buttons_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 20))
        bottom_buttons_frame.grid_columnconfigure((0, 1), weight=1)

        self.save_button = customtkinter.CTkButton(bottom_buttons_frame, text=self.app.translate("label_save"), command=self.confirm)
        self.save_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.cancel_button = customtkinter.CTkButton(bottom_buttons_frame, text=self.app.translate("label_cancel"), command=self.on_close, fg_color="gray50")
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.reset_button = customtkinter.CTkButton(
            bottom_buttons_frame, 
            text=self.app.translate("factory_reset_button"), 
            command=self.app.controller.factory_reset,
            fg_color="#E74C3C", 
            hover_color="#C0392B"
        )
        self.reset_button.grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky="ew")

    def populate_host_list(self):
        logging.debug("Populating host list for editing in TabSettingsDialog")
        for widget in self.host_frames:
            widget.destroy()
        self.host_frames = []
        
        for i, host in enumerate(self.hosts_local_list):
            container_frame = customtkinter.CTkFrame(self.scrollable_frame, fg_color=("gray85", "gray17"))
            container_frame.grid(row=i, column=0, sticky="ew", padx=5, pady=4)
            container_frame.grid_columnconfigure(3, weight=1)
            
            drag_handle = customtkinter.CTkLabel(container_frame, text="☰", cursor="hand2", font=customtkinter.CTkFont(size=16))
            drag_handle.grid(row=0, column=0, padx=10, pady=10)
            
            ip_title = customtkinter.CTkLabel(container_frame, text=self.app.translate("tab_settings_ip_label"))
            ip_title.grid(row=0, column=1, padx=(10, 2), pady=10, sticky="e")
            ip_entry = customtkinter.CTkEntry(container_frame, placeholder_text=host.get('ip', 'N/A'), width=160)
            ip_entry.insert(0, host.get('ip', ''))
            ip_entry.grid(row=0, column=2, padx=(2, 10), pady=10, sticky="w")
            
            nickname_entry = customtkinter.CTkEntry(container_frame, placeholder_text=host.get('name'))
            nickname = host.get('nickname', '')
            if nickname:
                nickname_entry.insert(0, nickname)
            nickname_entry.grid(row=0, column=3, padx=10, pady=10, sticky="ew")

            container_frame.host_data = host
            container_frame.nickname_entry = nickname_entry
            container_frame.ip_entry = ip_entry
            self.host_frames.append(container_frame)
            
            drag_handle.bind("<ButtonPress-1>", lambda event, widget=container_frame: self.start_drag(event, widget))
            drag_handle.bind("<B1-Motion>", self.do_drag)
            drag_handle.bind("<ButtonRelease-1>", self.end_drag)

    def start_drag(self, event, widget):
        logging.debug(f"Starting drag for widget: {widget}")
        self.drag_widget = widget
        self.drag_start_y = event.y_root

    def do_drag(self, event):
        if not self.drag_widget:
            logging.debug("do_drag called but no widget is being dragged.")
            return

        self.drag_widget.lift()
        y = self.drag_widget.winfo_y() + (event.y_root - self.drag_start_y)
        
        self.drag_widget.place(y=y, x=0, relwidth=1)
        
        self.drag_start_y = event.y_root

        target_index = -1
        for i, frame in enumerate(self.host_frames):
            if frame is self.drag_widget:
                continue
            
            if self.drag_widget.winfo_y() < frame.winfo_y() + frame.winfo_height() / 2:
                target_index = i
                self.drop_indicator.grid(row=target_index, column=0, sticky="ew", padx=5)
                logging.debug(f"Dragging widget. Potential target index: {target_index}")
                self.drop_indicator.lift()
                break
        else:
            target_index = len(self.host_frames)
            self.drop_indicator.grid(row=target_index, column=0, sticky="ew", padx=5)
            self.drop_indicator.lift()

    def end_drag(self, event):
        logging.debug("Ending drag operation")
        if not self.drag_widget:
            return
        
        self.drop_indicator.grid_forget()
        
        target_index = -1
        for i, frame in enumerate(self.host_frames):
            if frame is self.drag_widget:
                continue
            if self.drag_widget.winfo_y() < frame.winfo_y() + frame.winfo_height() / 2:
                target_index = i
                logging.debug(f"Drag ended. Determined target index: {target_index}")
                break
        
        self.drag_widget.place_forget()
        original_index = self.host_frames.index(self.drag_widget)
        
        dragged_frame = self.host_frames.pop(original_index)
        dragged_data = self.hosts_local_list.pop(original_index)
        
        if target_index != -1:
            if target_index > original_index:
                target_index -= 1
            self.host_frames.insert(target_index, dragged_frame)
            self.hosts_local_list.insert(target_index, dragged_data)
        else:
            self.host_frames.append(dragged_frame)
            self.hosts_local_list.append(dragged_data)

        for i, frame in enumerate(self.host_frames):
            frame.grid(row=i, column=0, sticky="ew", padx=5, pady=4)

        self.drag_widget = None
        logging.debug("Drag operation finished and UI re-gridded.")

    def confirm(self):
        try:
            interval_value = int(self.interval_entry.get())
            logging.debug(f"Confirming settings. Entered interval: {interval_value}, Ask initial info: {bool(self.ask_info_checkbox.get())}")
            if interval_value < 5:
                self.app.show_error(self.app.translate("error_invalid_interval"))
                return
            
            final_hosts_list = []
            for frame in self.host_frames:
                host_data = frame.host_data
                host_data['nickname'] = frame.nickname_entry.get().strip()
                # Atualizar IP se alterado
                new_ip = frame.ip_entry.get().strip()
                if new_ip:
                    host_data['ip'] = new_ip
                final_hosts_list.append(host_data)

            self.result_data = {
                "interval": interval_value,
                "updated_hosts": final_hosts_list,
                "ask_initial_info": bool(self.ask_info_checkbox.get())
            }
            logging.info(f"Tab settings confirmed. Result data: {self.result_data}")
            self.destroy()

        except (ValueError, TypeError):
            self.app.show_error(self.app.translate("error_invalid_interval"))
            logging.warning(f"Invalid interval value entered: {self.interval_entry.get()}")

    def on_close(self, event=None):
        self.result_data = None
        logging.info("Tab settings dialog closed without saving.")
        self.destroy()

    def get_selection(self):
        self.wait()
        return self.result_data