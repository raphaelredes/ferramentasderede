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
        self.grid_rowconfigure(2, weight=1)

        # Frame de controles com estilo aprimorado (sem título redundante)
        controls_frame = customtkinter.CTkFrame(self, fg_color=("gray90", "gray20"))
        controls_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 15))
        controls_frame.grid_columnconfigure(1, weight=1)

        self.period_label = customtkinter.CTkLabel(
            controls_frame,
            text=self.app.translate("activity_period_label"),
            font=customtkinter.CTkFont(weight="bold")
        )
        self.period_label.grid(row=0, column=0, padx=(15, 10), pady=12)

        self.period_combo = customtkinter.CTkComboBox(
            controls_frame,
            values=[
                self.app.translate("period_today"),
                self.app.translate("period_yesterday"),
                self.app.translate("period_this_week"),
                self.app.translate("period_last_week"),
                self.app.translate("period_this_month"),
                self.app.translate("period_last_month")
            ],
            width=200,
            font=customtkinter.CTkFont(size=13)
        )
        self.period_combo.set(self.app.translate("period_today"))
        self.period_combo.grid(row=0, column=1, padx=10, pady=12, sticky="ew")

        # Botão com estilo aprimorado
        analyze_color = self._get_theme_color("success_green", "#2ECC71")
        self.fetch_button = customtkinter.CTkButton(
            controls_frame,
            text=self.app.translate("activity_analyze_button"),
            command=self.fetch_data,
            fg_color=analyze_color,
            hover_color=self._get_theme_color("success_green", "#27AE60"),
            font=customtkinter.CTkFont(size=14, weight="bold"),
            height=32,
            width=120
        )
        self.fetch_button.grid(row=0, column=2, padx=(10, 15), pady=12)
        
        # Frame de resultados com melhor layout
        self.results_frame = customtkinter.CTkFrame(self, fg_color=("gray88", "gray19"))
        self.results_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        self.results_frame.grid_columnconfigure((0, 1), weight=1)

        # Título da seção de resultados
        results_title = customtkinter.CTkLabel(
            self.results_frame,
            text="📊 Métricas de Atividade",
            font=customtkinter.CTkFont(size=13, weight="bold")
        )
        results_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 8))

        # Métricas principais em cards
        self.active_time_value_label = self._create_metric_card(self.results_frame, self.app.translate("activity_active_time"), "00:00:00", "⚡", 1, 0)
        self.idle_time_value_label = self._create_metric_card(self.results_frame, self.app.translate("activity_idle_time"), "00:00:00", "💤", 1, 1)

        # Métricas avançadas em cards
        self.efficiency_label = self._create_metric_card(self.results_frame, "Eficiência de Uso", "0%", "🎯", 2, 0)
        self.uptime_label = self._create_metric_card(self.results_frame, "Tempo Ligado", "0%", "🔋", 2, 1)



        # Log textbox com melhor styling
        self.log_textbox = customtkinter.CTkTextbox(
            self,
            font=('Consolas', 10),
            fg_color=("gray95", "gray15"),
            border_width=1,
            border_color=("gray70", "gray30")
        )
        self.log_textbox.grid(row=2, column=0, sticky="nsew", padx=15, pady=(10, 10))
        self.log_textbox.configure(state="disabled")
        self._add_log(self.app.translate("activity_initial_prompt"))

    def _get_theme_color(self, color_key, fallback=None):
        """Obtém cores do sistema de tema para melhor contraste."""
        try:
            if hasattr(self.app, 'theme_enhancer') and self.app.theme_enhancer:
                return self.app.theme_enhancer.get_enhanced_color(color_key, fallback)
            else:
                return fallback or color_key
        except Exception as e:
            logging.debug(f"Erro ao obter cor do tema: {e}")
            return fallback or color_key

    def _create_metric_card(self, parent, label_text, value_text, icon, row, column):
        """Cria um card de métrica ultra-compacto."""
        # Frame do card ultra-compacto
        card_frame = customtkinter.CTkFrame(parent, fg_color=("gray92", "gray25"))
        card_frame.grid(row=row, column=column, padx=4, pady=2, sticky="ew")
        card_frame.grid_columnconfigure(0, weight=1)

        # Tudo em uma única linha
        content_frame = customtkinter.CTkFrame(card_frame, fg_color="transparent")
        content_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        content_frame.grid_columnconfigure(2, weight=1)

        icon_label = customtkinter.CTkLabel(
            content_frame,
            text=icon,
            font=customtkinter.CTkFont(size=10)
        )
        icon_label.grid(row=0, column=0, padx=(0, 2))

        label = customtkinter.CTkLabel(
            content_frame,
            text=label_text + ":",
            font=customtkinter.CTkFont(size=9),
            anchor="w"
        )
        label.grid(row=0, column=1, padx=(0, 4), sticky="w")

        value_label = customtkinter.CTkLabel(
            content_frame,
            text=value_text,
            font=customtkinter.CTkFont(size=11, weight="bold"),
            text_color=self._get_theme_color("success_green", "#2ECC71"),
            anchor="w"
        )
        value_label.grid(row=0, column=2, sticky="w")

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
            self.efficiency_label.configure(text="--")
            self.uptime_label.configure(text="--")
            self.ratio_progress.set(0)
            return

        active_time = results.get('active', timedelta(0))
        idle_time = results.get('idle', timedelta(0))
        total_time = active_time + idle_time

        # Métricas avançadas da nova implementação
        efficiency_ratio = results.get('efficiency_ratio', 0)
        uptime_ratio = results.get('uptime_ratio', 0)
        method_used = results.get('method_used', 'basic')
        system_uptime = results.get('system_uptime', timedelta(0))

        logging.debug(f"Updating activity UI for {self.host['name']} ({self.host['ip']}) with Advanced metrics: Active: {active_time}, Idle: {idle_time}, Efficiency: {efficiency_ratio:.1f}%, Uptime: {uptime_ratio:.1f}%, Method: {method_used}")

        # Formatar tempos de forma mais legível
        active_str = self._format_timedelta(active_time)
        idle_str = self._format_timedelta(idle_time)

        self.active_time_value_label.configure(text=active_str)
        self.idle_time_value_label.configure(text=idle_str)

        # Atualizar métricas avançadas
        self.efficiency_label.configure(text=f"{efficiency_ratio:.1f}%")
        self.uptime_label.configure(text=f"{uptime_ratio:.1f}%")

        if total_time.total_seconds() > 0:
            # Log detalhado com nova funcionalidade aprimorado
            if method_used == 'advanced_analysis':
                self._add_log("🎯 ANÁLISE AVANÇADA - Sistema de cálculo aprimorado ativo")
                self._add_log(f"🔋 Sistema ligado: {self._format_timedelta(system_uptime)} ({uptime_ratio:.1f}% do período)")
                self._add_log(f"⚡ Eficiência de uso: {efficiency_ratio:.1f}% do tempo disponível")
                self._add_log(f"✅ Atividade: {active_str} ({efficiency_ratio:.1f}%)")
                self._add_log(f"💤 Ociosidade: {idle_str} ({100-efficiency_ratio:.1f}%)")

                # Log de eventos encontrados para diagnóstico
                event_count = results.get('event_count', 0)
                detection_method = results.get('detection_method', 'standard')
                self._add_log(f"📊 Eventos analisados: {event_count}, Método: {detection_method}")

                if detection_method in ['smart_detection', 'process_inference']:
                    self._add_log("🔍 Detecção inteligente utilizada - Atividade inferida a partir de processos ativos")
                elif event_count == 0:
                    self._add_log("⚠️ Nenhum evento de log encontrado - Verificar política de auditoria")
            else:
                active_percent = (active_time.total_seconds() / total_time.total_seconds()) * 100
                self._add_log(f"✅ Análise básica: {active_percent:.1f}% ativo, {100-active_percent:.1f}% ocioso")
        else:
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
        """Atualiza os textos da interface quando o idioma muda."""
        # Atualizar título (seria necessário armazenar referência se quiséssemos atualizar)

        # Atualizar controles
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

        # Nota: Como os cards são criados dinamicamente, uma atualização completa
        # seria necessária para mudar os labels dos cards, mas os valores principais
        # são atualizados quando os dados são carregados