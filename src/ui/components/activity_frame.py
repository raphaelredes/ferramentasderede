# app/ui_components/activity_frame.py

import customtkinter
from datetime import timedelta, datetime
import logging

class ActivityFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host, tool_controller):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.host = host
        self.tool_controller = tool_controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # Mudou de 2 para 3 para acomodar o aviso

        controls_frame = customtkinter.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure(1, weight=1)

        self.period_label = customtkinter.CTkLabel(controls_frame, text=self.app.translate("activity_period_label"))
        self.period_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.period_combo = customtkinter.CTkComboBox(
            controls_frame,
            values=[
                self.app.translate("period_today"), 
                self.app.translate("period_yesterday"), 
                self.app.translate("period_this_week"), 
                self.app.translate("period_last_week"), 
                self.app.translate("period_this_month"), 
                self.app.translate("period_last_month")
            ]
        )
        self.period_combo.set(self.app.translate("period_today"))
        self.period_combo.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.fetch_button = customtkinter.CTkButton(controls_frame, text=self.app.translate("activity_analyze_button"), command=self.fetch_data)
        self.fetch_button.grid(row=0, column=2, padx=(5, 10), pady=10)
        
        self.results_frame = customtkinter.CTkFrame(self, fg_color=("gray85", "gray17"))
        self.results_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0,10))
        self.results_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.active_time_value_label = self._create_result_label(self.results_frame, self.app.translate("activity_active_time"), "00:00:00", 0)
        self.idle_time_value_label = self._create_result_label(self.results_frame, self.app.translate("activity_idle_time"), "00:00:00", 1)
        
        self.ratio_progress = customtkinter.CTkProgressBar(self.results_frame, progress_color="#2ECC71")
        self.ratio_progress.grid(row=2, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="ew")
        self.ratio_progress.set(0)

        # Aviso de funcionalidade em desenvolvimento
        self.dev_warning_frame = customtkinter.CTkFrame(self, fg_color=("orange", "darkorange"))
        self.dev_warning_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.dev_warning_frame.grid_columnconfigure(0, weight=1)
        
        warning_text = "⚠️ FUNCIONALIDADE EM DESENVOLVIMENTO - Esta funcionalidade está sendo aprimorada e pode apresentar resultados experimentais."
        self.dev_warning_label = customtkinter.CTkLabel(
            self.dev_warning_frame, 
            text=warning_text,
            font=customtkinter.CTkFont(size=12, weight="bold"),
            text_color=("black", "white")
        )
        self.dev_warning_label.grid(row=0, column=0, padx=15, pady=10, sticky="ew")

        self.log_textbox = customtkinter.CTkTextbox(self, font=('Consolas', 12))
        self.log_textbox.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.log_textbox.configure(state="disabled")
        self._add_log("🔧 FUNCIONALIDADE EM DESENVOLVIMENTO - Detecção de atividade sendo aprimorada")
        self._add_log(self.app.translate("activity_initial_prompt"))

    def _create_result_label(self, parent, text, value_text, row):
        label = customtkinter.CTkLabel(parent, text=text, font=customtkinter.CTkFont(weight="bold"))
        label.grid(row=row, column=0, padx=10, pady=5, sticky="e")
        value_label = customtkinter.CTkLabel(parent, text=value_text, font=customtkinter.CTkFont(size=14))
        value_label.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        return value_label

    def fetch_data(self):
        period_str_translated = self.period_combo.get()
        logging.info(f"Fetching activity data for {self.host['name']} ({self.host['ip']}) for period: {period_str_translated}")
        self._add_log(self.app.translate("activity_log_starting", period=period_str_translated))
        self.tool_controller.fetch_activity_data(period_str_translated, self.update_ui_with_results)

    def update_ui_with_results(self, results):
        if "error" in results:
            logging.error(f"Error fetching activity data for {self.host['name']} ({self.host['ip']}): {results['error']}")
            self._add_log(self.app.translate("activity_log_error", error=results['error']))
            self.active_time_value_label.configure(text="--:--:--")
            self.idle_time_value_label.configure(text="--:--:--")
            self.ratio_progress.set(0)
            return

        active_time = results.get('active', timedelta(0))
        idle_time = results.get('idle', timedelta(0))
        total_time = active_time + idle_time
        logging.debug(f"Updating activity UI for {self.host['name']} ({self.host['ip']}) with Active: {active_time}, Idle: {idle_time}")

        # Formatar tempos de forma mais legível
        active_str = self._format_timedelta(active_time)
        idle_str = self._format_timedelta(idle_time)
        
        self.active_time_value_label.configure(text=active_str)
        self.idle_time_value_label.configure(text=idle_str)

        if total_time.total_seconds() > 0:
            ratio = active_time.total_seconds() / total_time.total_seconds()
            self.ratio_progress.set(ratio)
            
            # Adicionar informações detalhadas
            active_percent = (active_time.total_seconds() / total_time.total_seconds()) * 100
            self._add_log(f"✅ Análise concluída: {active_percent:.1f}% ativo, {100-active_percent:.1f}% ocioso")
        else:
            self.ratio_progress.set(0)
            self._add_log(self.app.translate("activity_log_no_events"))
            logging.info(f"No activity events found for {self.host['name']} ({self.host['ip']}) for the selected period.")
            return
            
        self._add_log(self.app.translate("activity_log_done"))
        logging.info(f"Finished updating activity UI for {self.host['name']} ({self.host['ip']}).")

    def _format_timedelta(self, td):
        """Formata um timedelta em formato legível HH:MM:SS"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _add_log(self, message):
        self.log_textbox.configure(state="normal")
        logging.debug(f"Activity Log: {message}")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        
    def update_language(self):
        self.period_label.configure(text=self.app.translate("activity_period_label"))
        
        translated_values = [
            self.app.translate("period_today"), 
            self.app.translate("period_yesterday"), 
            self.app.translate("period_this_week"), 
            self.app.translate("period_last_week"), 
            self.app.translate("period_this_month"), 
            self.app.translate("period_last_month")
        ]
        
        current_selection = self.period_combo.get()
        self.period_combo.configure(values=translated_values)
        
        if current_selection in translated_values:
            self.period_combo.set(current_selection)
        else:
            self.period_combo.set(self.app.translate("period_today"))

        self.fetch_button.configure(text=self.app.translate("activity_analyze_button"))
        self.active_time_value_label.master.winfo_children()[0].configure(text=self.app.translate("activity_active_time"))
        self.idle_time_value_label.master.winfo_children()[2].configure(text=self.app.translate("activity_idle_time"))