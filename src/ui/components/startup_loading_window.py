# src/ui/components/startup_loading_window.py
# Janela de carregamento específica para inicialização da aplicação

import customtkinter
import logging
import threading
import time

class StartupLoadingWindow(customtkinter.CTkToplevel):
    """Janela de carregamento otimizada para inicialização da aplicação."""

    def __init__(self, master=None):
        # Se não há master, criar uma janela root oculta temporária
        if master is None:
            self._hidden_root = customtkinter.CTk()
            self._hidden_root.withdraw()  # Ocultar imediatamente
            master = self._hidden_root
        else:
            self._hidden_root = None

        super().__init__(master)

        # Configurações da janela
        self.title("Ferramentas de Rede")
        self.geometry("450x250")
        self.resizable(False, False)

        # Centralizar na tela
        self._center_window()

        # Configurar como modal
        self.transient(master)
        self.grab_set()

        # Flags de controle
        self._is_closed = False
        self._current_step = 0
        self._total_steps = 4
        self._start_time = time.time()

        # Criar interface otimizada
        self._create_widgets()

        # Configurar protocolos
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Aplicar tema consistente
        self._apply_theme()

        logging.info("Janela de carregamento de inicialização criada")

    def _center_window(self):
        """Centraliza a janela na tela com posicionamento otimizado."""
        try:
            # Obter dimensões da tela
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            # Calcular posição central
            x = (screen_width - 450) // 2
            y = (screen_height - 250) // 2

            # Garantir que não saia da tela
            x = max(0, min(x, screen_width - 450))
            y = max(0, min(y, screen_height - 250))

            self.geometry(f"450x250+{x}+{y}")

        except Exception as e:
            logging.error(f"Erro ao centralizar janela: {e}")
            # Fallback para posição padrão
            self.geometry("450x250+500+300")

    def _create_widgets(self):
        """Cria os widgets da interface otimizada."""
        # Frame principal com cor de fundo
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=25, pady=25)

        # Logo/Ícone (placeholder)
        icon_frame = customtkinter.CTkFrame(main_frame, height=50, fg_color="transparent")
        icon_frame.pack(pady=(5, 10), fill="x")

        # Título principal
        title_label = customtkinter.CTkLabel(
            icon_frame,
            text="🛠️ Ferramentas de Rede",
            font=customtkinter.CTkFont(size=22, weight="bold")
        )
        title_label.pack()

        # Subtítulo com versão
        subtitle_label = customtkinter.CTkLabel(
            main_frame,
            text="Versão 1.1.0 - Sistema Profissional de Rede",
            font=customtkinter.CTkFont(size=12),
            text_color=("gray60", "gray50")
        )
        subtitle_label.pack(pady=(0, 20))

        # Status do carregamento
        self.status_label = customtkinter.CTkLabel(
            main_frame,
            text="Inicializando sistema...",
            font=customtkinter.CTkFont(size=14, weight="bold")
        )
        self.status_label.pack(pady=(15, 10))

        # Label de progresso detalhado
        self.detail_label = customtkinter.CTkLabel(
            main_frame,
            text="Preparando componentes...",
            font=customtkinter.CTkFont(size=12),
            text_color=("gray60", "gray50")
        )
        self.detail_label.pack(pady=(0, 15))

        # Tempo estimado
        self.time_label = customtkinter.CTkLabel(
            main_frame,
            text="",
            font=customtkinter.CTkFont(size=10),
            text_color=("gray50", "gray60")
        )
        self.time_label.pack(pady=(0, 5))

    def _apply_theme(self):
        """Aplica tema consistente à janela."""
        try:
            # Configurar cor de fundo baseada no tema atual
            appearance_mode = customtkinter.get_appearance_mode()
            if appearance_mode.lower() == "dark":
                bg_color = "#212121"
            else:
                bg_color = "#f0f0f0"

            self.configure(fg_color=bg_color)

            # Aplicar efeito de sombra (se suportado)
            self.attributes("-alpha", 0.95)

        except Exception as e:
            logging.debug(f"Erro ao aplicar tema: {e}")

    def update_status(self, status_text, detail_text="", progress=None):
        """Atualiza o status do carregamento com informações aprimoradas."""
        if self._is_closed:
            return

        try:
            if self.winfo_exists():
                # Atualizar status principal
                self.status_label.configure(text=status_text)

                # Atualizar detalhes se fornecidos
                if detail_text:
                    self.detail_label.configure(text=detail_text)

                # Calcular e mostrar tempo estimado (baseado em tempo decorrido)
                self._update_time_estimate(progress)

                self.update_idletasks()

        except Exception as e:
            logging.debug(f"Erro ao atualizar status: {e}")

    def _update_time_estimate(self, progress):
        """Atualiza estimativa de tempo restante."""
        try:
            if progress and progress > 0.1:  # Só mostrar após 10% para ter estimativa confiável
                elapsed_time = time.time() - self._start_time
                estimated_total = elapsed_time / progress
                remaining_time = estimated_total - elapsed_time

                if remaining_time > 0:
                    if remaining_time < 60:
                        time_text = f"~{int(remaining_time)}s restantes"
                    else:
                        minutes = int(remaining_time // 60)
                        seconds = int(remaining_time % 60)
                        time_text = f"~{minutes}m {seconds}s restantes"

                    self.time_label.configure(text=time_text)
                else:
                    self.time_label.configure(text="Finalizando...")

        except Exception as e:
            logging.debug(f"Erro ao calcular tempo: {e}")

    def update_step(self, step_name, detail=""):
        """Atualiza o passo atual do carregamento."""
        if self._is_closed:
            return

        self._current_step += 1

        status_text = f"Passo {self._current_step}/{self._total_steps}: {step_name}"
        self.update_status(status_text, detail)

        logging.info(f"Loading step {self._current_step}/{self._total_steps}: {step_name}")

    def set_final_step(self, message="Finalizando..."):
        """Define o passo final com transição suave antes de fechar."""
        if self._is_closed:
            return

        # Passo final com animação de conclusão
        self.update_status(message, "Aplicação pronta! Iniciando interface...")

        # Adicionar efeito de fade out suave
        self.after(300, self._start_fade_out)

    def _start_fade_out(self):
        """Inicia efeito de fade out suave."""
        try:
            # Efeito de fade out em 3 passos
            self._fade_step = 0
            self._do_fade_step()
        except Exception as e:
            logging.debug(f"Erro no fade out: {e}")
            self._finish_loading()

    def _do_fade_step(self):
        """Executa um passo do fade out."""
        try:
            fade_levels = [0.8, 0.5, 0.2]

            if self._fade_step < len(fade_levels):
                self.attributes("-alpha", fade_levels[self._fade_step])
                self._fade_step += 1
                self.after(100, self._do_fade_step)
            else:
                self._finish_loading()

        except Exception as e:
            logging.debug(f"Erro no fade step: {e}")
            self._finish_loading()

    def _finish_loading(self):
        """Finaliza o carregamento e fecha a janela."""
        logging.info("Finalizando janela de carregamento")
        self.close()

    def close(self):
        """Fecha a janela de carregamento com transição suave."""
        if self._is_closed:
            return

        self._is_closed = True

        try:
            # Restore alpha antes de fechar para evitar problemas
            self.attributes("-alpha", 1.0)

            # Liberar grab e fechar
            self.grab_release()

            # Destruir imediatamente para garantir fechamento completo
            self._safe_destroy()

        except Exception as e:
            logging.error(f"Erro ao fechar janela de carregamento: {e}")
            self._safe_destroy()

    def _safe_destroy(self):
        """Destrói a janela de forma segura."""
        try:
            self.destroy()

            # Se criamos uma janela root oculta, destruí-la também
            if hasattr(self, '_hidden_root') and self._hidden_root:
                try:
                    self._hidden_root.withdraw()  # Ocultar primeiro
                    self._hidden_root.quit()     # Sair do mainloop se houver
                    self._hidden_root.destroy()  # Destruir a janela
                    self._hidden_root = None     # Limpar referência
                    logging.debug("Janela root oculta destruída com sucesso")
                except Exception as e:
                    logging.debug(f"Erro ao destruir janela root oculta: {e}")

            logging.info("Janela de carregamento fechada")
        except Exception as e:
            logging.debug(f"Erro ao destruir janela: {e}")

    def _on_close(self):
        """Previne o fechamento manual da janela."""
        # Durante o carregamento, não permitir fechamento manual
        logging.debug("Tentativa de fechamento manual da janela de carregamento ignorada")
        pass

    def is_closed(self):
        """Verifica se a janela foi fechada."""
        return self._is_closed or not self.winfo_exists()

class StartupManager:
    """Gerenciador de inicialização da aplicação."""

    def __init__(self, app_class, base_dir):
        self.app_class = app_class
        self.base_dir = base_dir
        self.loading_window = None
        self.app_instance = None
        self.host_data = {}
        self.loading_complete = False

    def start_application(self):
        """Inicia a aplicação com janela de carregamento."""
        try:
            logging.info("Iniciando aplicação com janela de carregamento")

            # Criar janela de carregamento primeiro
            self.loading_window = StartupLoadingWindow()
            self.loading_window.update_status("Inicializando aplicação...")

            # Atualizar display para mostrar a janela
            self.loading_window.update()

            # Iniciar carregamento usando threading para não bloquear UI
            self.loading_window.after(200, self._start_background_initialization)

            # Iniciar mainloop da janela de carregamento
            self.loading_window.mainloop()

            # Após fechar a janela de carregamento, iniciar aplicação principal
            if self.app_instance:
                logging.info("=== INICIANDO APLICAÇÃO PRINCIPAL ===")

                # Pequeno delay para garantir que a janela de carregamento foi completamente fechada
                import time
                time.sleep(0.1)

                self.app_instance.run()
                logging.info("=== APLICAÇÃO PRINCIPAL FINALIZADA ===")

        except Exception as e:
            logging.error(f"Erro ao iniciar aplicação: {e}")
            if self.loading_window:
                self.loading_window.close()
            raise

    def _start_background_initialization(self):
        """Inicia a inicialização de forma sequencial na thread principal."""
        try:
            logging.info("Iniciando inicialização sequencial...")
            self.loading_step = 0
            self._next_initialization_step()

        except Exception as e:
            logging.error(f"Erro ao iniciar background: {e}")
            self.loading_window.close()

    def _next_initialization_step(self):
        """Executa o próximo passo da inicialização."""
        try:
            if self.loading_step == 0:
                # Passo 1: Preparar ambiente
                self.loading_window.update_status("Preparando ambiente", "Configurando sistema...")
                self.loading_step = 1
                self.loading_window.after(200, self._next_initialization_step)

            elif self.loading_step == 1:
                # Passo 2: Criar instância da aplicação
                self.loading_window.update_status("Criando aplicação", "Inicializando componentes...")
                try:
                    self.app_instance = self.app_class(self.base_dir, None)
                    logging.info("Instância da aplicação criada com sucesso")
                    self.loading_step = 2
                    self.loading_window.after(300, self._next_initialization_step)
                except Exception as e:
                    logging.error(f"Erro ao criar aplicação: {e}")
                    self.loading_window.close()

            elif self.loading_step == 2:
                # Passo 3: Carregar dados dos hosts em background usando threading
                self.loading_window.update_status("Carregando hosts", "Verificando hosts disponíveis...")
                self._start_host_loading()

            elif self.loading_step == 3:
                # Passo 4: Finalizar
                self.loading_window.update_status("Finalizando", "Aplicação quase pronta...")
                self.loading_complete = True
                self.loading_window.after(500, self._finish_and_start_app)

        except Exception as e:
            logging.error(f"Erro no passo {self.loading_step}: {e}")
            self.loading_window.close()

    def _start_host_loading(self):
        """Inicia carregamento de hosts em thread separada."""
        import threading

        def load_hosts_worker():
            try:
                if hasattr(self.app_instance, 'controller'):
                    # Callback para atualizar status
                    def update_callback(message):
                        self.loading_window.after(0, lambda: self.loading_window.update_status("Carregando hosts", message))

                    # Carregar dados dos hosts
                    self.app_instance.controller.load_and_prepare_all_hosts(update_callback)
                    logging.info("Dados dos hosts carregados com sucesso")
                else:
                    logging.warning("Controller não disponível")

            except Exception as e:
                logging.error(f"Erro ao carregar hosts: {e}")
            finally:
                # Notificar aplicação que dados estão prontos
                if hasattr(self.app_instance, '_on_data_loaded'):
                    self.app_instance._on_data_loaded()

                # Avançar para próximo passo na thread principal
                self.loading_window.after(0, self._host_loading_complete)

        # Iniciar thread para carregamento
        host_thread = threading.Thread(target=load_hosts_worker, daemon=True, name="HostLoader")
        host_thread.start()

    def _host_loading_complete(self):
        """Chamado quando carregamento de hosts é concluído."""
        self.loading_step = 3
        self._next_initialization_step()

    def _update_loading_status(self, status, detail):
        """Atualiza o status da janela de loading de forma thread-safe."""
        try:
            if self.loading_window and not self.loading_window.is_closed():
                # Usar after() para atualizar na thread principal
                self.loading_window.after(0, lambda: self.loading_window.update_status(status, detail))
        except Exception as e:
            logging.debug(f"Erro ao atualizar status: {e}")

    def _monitor_initialization_progress(self):
        """Monitora o progresso da inicialização e finaliza quando pronto."""
        try:
            if self.loading_complete:
                # Inicialização concluída, finalizar janela de loading
                self.loading_window.set_final_step("Aplicação pronta!")
                self.loading_window.after(500, self._finish_and_start_app)
            else:
                # Continuar monitorando
                self.loading_window.after(100, self._monitor_initialization_progress)

        except Exception as e:
            logging.error(f"Erro no monitoramento: {e}")
            self.loading_window.close()

    def _finish_and_start_app(self):
        """Finaliza a janela de carregamento."""
        try:
            logging.info("Finalizando janela de carregamento e preparando transição...")

            # Fechar janela de carregamento primeiro
            self.loading_window.close()

            # Agendar quit para depois do fechamento estar completo
            def delayed_quit():
                try:
                    logging.info("Executando quit() da janela de carregamento")
                    self.loading_window.quit()
                except Exception as e:
                    logging.debug(f"Erro no delayed_quit: {e}")

            # Usar after com delay maior para garantir fechamento completo
            self.loading_window.after(200, delayed_quit)

        except Exception as e:
            logging.error(f"Erro ao finalizar: {e}")
            # Garantir que quit seja chamado mesmo em caso de erro
            try:
                self.loading_window.quit()
            except:
                pass

