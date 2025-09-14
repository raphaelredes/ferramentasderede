# src/ferramentasderede/ui/components/info_widgets.py

import customtkinter
import webbrowser
from tkinter import messagebox
from src.config.settings import APP_VERSION
from .base_dialog import BaseDialog
import time

class HostInfoDisplay(customtkinter.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=("gray85", "gray17"), corner_radius=10)
        self.app = app
        self._secondary_ip_cache = {}
        self.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="group1")
        self.grid_rowconfigure(0, weight=1)

        ip_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        ip_frame.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")
        self.ip_label_title = customtkinter.CTkLabel(ip_frame, text=self.app.translate("IP:"), font=customtkinter.CTkFont(size=13, weight="bold"))
        self.ip_label_title.pack(pady=(5, 0))
        self.ip_label_value = customtkinter.CTkLabel(ip_frame, text="...", anchor="center")
        self.ip_label_value.pack(pady=(0, 5), padx=5, fill="x")
        # Inline secondary IP (confirmed) directly below main IP
        self.secondary_ip_inline = customtkinter.CTkLabel(ip_frame, text="", anchor="center")
        self.secondary_ip_inline.pack(pady=(0, 5), padx=5, fill="x")

        subnet_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        subnet_frame.grid(row=0, column=1, padx=5, pady=10, sticky="nsew")
        self.subnet_label_title = customtkinter.CTkLabel(subnet_frame, text=self.app.translate("Máscara de Rede:"), font=customtkinter.CTkFont(size=13, weight="bold"))
        self.subnet_label_title.pack(pady=(5, 0))
        self.subnet_label_value = customtkinter.CTkLabel(subnet_frame, text="...", anchor="center")
        self.subnet_label_value.pack(pady=(0, 5), padx=5, fill="x")

        hostname_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        hostname_frame.grid(row=0, column=2, padx=5, pady=10, sticky="nsew")
        self.hostname_label_title = customtkinter.CTkLabel(hostname_frame, text=self.app.translate("Hostname:"), font=customtkinter.CTkFont(size=13, weight="bold"))
        self.hostname_label_title.pack(pady=(5, 0))
        self.hostname_label_value = customtkinter.CTkLabel(hostname_frame, text="...", anchor="center")
        self.hostname_label_value.pack(pady=(0, 5), padx=5, fill="x")

        tv_id_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        tv_id_frame.grid(row=0, column=3, padx=5, pady=10, sticky="nsew")
        self.tv_id_label_title = customtkinter.CTkLabel(tv_id_frame, text=self.app.translate("TeamViewer ID:"), font=customtkinter.CTkFont(size=13, weight="bold"))
        self.tv_id_label_title.pack(pady=(5, 0))
        self.tv_id_label_value = customtkinter.CTkLabel(tv_id_frame, text="...", anchor="center")
        self.tv_id_label_value.pack(pady=(0, 5), padx=5, fill="x")

    def update_info(self, ip=None, subnet_mask=None, hostname=None, tv_id=None, secondary_ips=None):
        if ip is not None: self.ip_label_value.configure(text=ip)
        if subnet_mask is not None: self.subnet_label_value.configure(text=subnet_mask)
        if hostname is not None: self.hostname_label_value.configure(text=hostname)
        if tv_id is not None: self.tv_id_label_value.configure(text=tv_id)
        # Atualizar exibição do IP secundário confirmado (inline) sem tooltip
        try:
            if secondary_ips:
                # Preparar lista para tooltip
                items = []
                candidate_ip = None
                candidate_label = None
                for entry in secondary_ips:
                    if isinstance(entry, dict):
                        ip_val = entry.get('ip')
                        lbl = entry.get('label') or '-'
                        if ip_val and not candidate_ip:
                            candidate_ip, candidate_label = ip_val, lbl
                        items.append(f"• {ip_val}  [{lbl}]")
                    else:
                        ip_val = str(entry)
                        if ip_val and not candidate_ip:
                            candidate_ip = ip_val
                        items.append(f"• {ip_val}")

                # Confirmar candidato com um ping rápido em thread separada
                def confirm_and_set():
                    try:
                        if not candidate_ip:
                            self.app.after(0, lambda: self.secondary_ip_inline.configure(text=""))
                            return
                        # Cache com TTL para evitar pings repetidos
                        ttl_seconds = 60
                        cached = self._secondary_ip_cache.get(candidate_ip)
                        now = time.time()
                        if cached and now - cached[1] < ttl_seconds:
                            is_up = cached[0]
                        else:
                            # Usar NetworkTools do controller para checagem rápida
                            is_up = self.app.controller.network_tools.check_host_status(candidate_ip)
                            self._secondary_ip_cache[candidate_ip] = (is_up, now)
                        if is_up:
                            text = candidate_ip if not candidate_label else f"{candidate_ip}  [{candidate_label}]"
                            self.app.after(0, lambda t=text: self.secondary_ip_inline.configure(text=t))
                        else:
                            self.app.after(0, lambda: self.secondary_ip_inline.configure(text=""))
                    except Exception:
                        self.app.after(0, lambda: self.secondary_ip_inline.configure(text=""))

                import threading
                threading.Thread(target=confirm_and_set, daemon=True).start()
            else:
                self.secondary_ip_inline.configure(text="")
        except Exception:
            pass

    def update_language(self):
        self.ip_label_title.configure(text=self.app.translate("IP:"))
        self.subnet_label_title.configure(text=self.app.translate("Máscara de Rede:"))
        self.hostname_label_title.configure(text=self.app.translate("Hostname:"))
        self.tv_id_label_title.configure(text=self.app.translate("TeamViewer ID:"))

class AboutDialog(BaseDialog):
    def __init__(self, app):
        super().__init__(app, title=app.translate("title_about"))
        
        # Definir tamanho mínimo adequado para o conteúdo
        self.minsize(550, 500)
        
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        title_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5,10))
        title_frame.grid_columnconfigure(0, weight=1)

        title_label = customtkinter.CTkLabel(title_frame, text=self.app.translate("title_about"), font=customtkinter.CTkFont(size=16, weight="bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        close_button_top = customtkinter.CTkButton(title_frame, text="✕", width=28, height=28, command=self.destroy, fg_color="transparent")
        close_button_top.grid(row=0, column=1, sticky="e")

        tab_view = customtkinter.CTkTabview(main_frame, anchor="w")
        tab_view.grid(row=1, column=0, sticky="nsew")

        tab_about = tab_view.add(self.app.translate("about_tab_about"))
        tab_about.grid_rowconfigure(0, weight=1)
        tab_about.grid_columnconfigure(0, weight=1)
        
        about_scroll_frame = customtkinter.CTkScrollableFrame(tab_about, fg_color="transparent")
        about_scroll_frame.grid(row=0, column=0, sticky="nsew", padx=5)

        app_title_label = customtkinter.CTkLabel(about_scroll_frame, text=self.app.translate("title_app"), font=customtkinter.CTkFont(size=20, weight="bold"))
        app_title_label.pack(pady=(15, 5))
        
        version_label = customtkinter.CTkLabel(about_scroll_frame, text=self.app.translate("about_version", version=APP_VERSION), font=customtkinter.CTkFont(size=12))
        version_label.pack(pady=(0, 10))
        
        desc_label = customtkinter.CTkLabel(about_scroll_frame, text=self.app.translate("about_description"), wraplength=450)
        desc_label.pack(pady=10, padx=20)
        
        features_frame = customtkinter.CTkFrame(about_scroll_frame, fg_color="transparent")
        features_frame.pack(pady=10, padx=20, fill="x")
        
        features_title = customtkinter.CTkLabel(features_frame, text=self.app.translate("about_features_title"), font=customtkinter.CTkFont(size=13, weight="bold"))
        features_title.pack()
        
        features_list = customtkinter.CTkLabel(features_frame, text=self.app.translate("about_features_list"), wraplength=400, justify="left")
        features_list.pack(pady=5)

        tab_credits = tab_view.add(self.app.translate("about_tab_credits"))
        credits_frame = customtkinter.CTkFrame(tab_credits, fg_color="transparent")
        credits_frame.pack(pady=20, padx=20, fill="both", expand=True)

        dev_by_prefix_label = customtkinter.CTkLabel(credits_frame, text=self.app.translate("about_developed_by"), font=customtkinter.CTkFont(size=13))
        dev_by_prefix_label.pack(pady=(10, 5))

        def open_telegram_link(event=None):
            webbrowser.open_new("https://t.me/raphaelrego")

        author_name_label = customtkinter.CTkLabel(credits_frame, text="Raphael Oliveira Rêgo", font=customtkinter.CTkFont(size=14, weight="bold", underline=True), text_color=("#3B8ED0", "#4FA8FF"), cursor="hand2")
        author_name_label.pack()
        author_name_label.bind("<Button-1>", open_telegram_link)

        def copy_email_to_clipboard(event=None):
            email = "raphael.redes@yahoo.com.br"
            self.app.clipboard_clear()
            self.app.clipboard_append(email)
            self.app.show_toast_notification(self.app.translate("email_copied_toast"))

        email_label = customtkinter.CTkLabel(credits_frame, text="raphael.redes@yahoo.com.br", font=customtkinter.CTkFont(size=12, underline=True), text_color=("#3B8ED0", "#4FA8FF"), cursor="hand2")
        email_label.pack(pady=(2, 20))
        email_label.bind("<Button-1>", copy_email_to_clipboard)

        ai_assistance_label = customtkinter.CTkLabel(credits_frame, text=self.app.translate("about_ai_assistance"), font=customtkinter.CTkFont(size=12, slant="italic"), text_color="white")
        ai_assistance_label.pack(pady=(15, 10))

        close_button_bottom = customtkinter.CTkButton(main_frame, text=self.app.translate("label_close"), command=self.destroy)
        close_button_bottom.grid(row=2, column=0, pady=(10, 10), padx=50, sticky="ew")

        self.bind("<Escape>", lambda e: self.destroy())

def show_about_popup(app):
    dialog = AboutDialog(app)
    app.wait_window(dialog)