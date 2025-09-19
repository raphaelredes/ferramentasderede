# src/ui/components/simple_loading.py
# Tela de loading simples e confiável

import customtkinter
import logging
import threading
import time

class SimpleLoadingWindow:
    """Tela de loading simples e confiável."""

    def __init__(self):
        self.window = None
        self.progress_var = None
        self.status_label = None
        self.progress_bar = None
        self.is_closed = False

    def create_window(self, master=None):
        """Cria a janela de loading."""
        try:
            # Criar janela com master adequado
            if master is None:
                # Criar uma janela root oculta se necessário
                self._hidden_root = customtkinter.CTk()
                self._hidden_root.withdraw()
                master = self._hidden_root
            else:
                self._hidden_root = None

            self.window = customtkinter.CTkToplevel(master)
            self.window.title("Ferramentas de Rede - Carregando")
            self.window.geometry("450x200")
            self.window.resizable(False, False)

            # Centralizar na tela
            self._center_window()

            # Configurar como modal
            self.window.transient()
            self.window.grab_set()

            # Prevenir fechamento manual
            self.window.protocol("WM_DELETE_WINDOW", lambda: None)

            # Criar interface
            self._create_interface()

            logging.info("Janela de loading criada com sucesso")
            return True

        except Exception as e:
            logging.error(f"Erro ao criar janela de loading: {e}")
            return False

    def _center_window(self):
        """Centraliza a janela na tela."""
        try:
            # Obter dimensões da tela
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()

            # Calcular posição central
            x = (screen_width - 450) // 2
            y = (screen_height - 200) // 2

            self.window.geometry(f"450x200+{x}+{y}")

        except Exception as e:
            logging.error(f"Erro ao centralizar janela: {e}")

    def _create_interface(self):
        """Cria a interface da janela."""
        try:
            # Frame principal
            main_frame = customtkinter.CTkFrame(self.window, fg_color="transparent")
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)

            # Título
            title_label = customtkinter.CTkLabel(
                main_frame,
                text="Ferramentas de Rede",
                font=customtkinter.CTkFont(size=18, weight="bold")
            )
            title_label.pack(pady=(5, 10))

            # Subtítulo
            subtitle_label = customtkinter.CTkLabel(
                main_frame,
                text="Versão 1.1.0 - Inicializando sistema...",
                font=customtkinter.CTkFont(size=11)
            )
            subtitle_label.pack(pady=(0, 15))

            # Status
            self.status_label = customtkinter.CTkLabel(
                main_frame,
                text="Preparando aplicação...",
                font=customtkinter.CTkFont(size=12)
            )
            self.status_label.pack(pady=10)

            # Barra de progresso
            self.progress_bar = customtkinter.CTkProgressBar(main_frame)
            self.progress_bar.pack(pady=10, fill="x")
            self.progress_bar.set(0)

            # Atualizar display
            self.window.update()

        except Exception as e:
            logging.error(f"Erro ao criar interface: {e}")

    def update_status(self, message, progress=None):
        """Atualiza o status da tela de loading."""
        if self.is_closed or not self.window:
            return

        try:
            if self.status_label:
                self.status_label.configure(text=message)

            if progress is not None and self.progress_bar:
                self.progress_bar.set(progress)

            self.window.update()

        except Exception as e:
            logging.error(f"Erro ao atualizar status: {e}")

    def close(self):
        """Fecha a janela de loading."""
        if self.is_closed:
            return

        try:
            self.is_closed = True

            if self.window:
                self.window.grab_release()
                self.window.destroy()

            # Limpar janela root oculta se foi criada
            if hasattr(self, '_hidden_root') and self._hidden_root:
                try:
                    self._hidden_root.destroy()
                except Exception as e:
                    logging.debug(f"Erro ao destruir janela root oculta: {e}")

            logging.info("Janela de loading fechada")

        except Exception as e:
            logging.error(f"Erro ao fechar janela: {e}")

    def show(self):
        """Mostra a janela de loading."""
        if not self.window:
            return False

        try:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return True

        except Exception as e:
            logging.error(f"Erro ao mostrar janela: {e}")
            return False

def test_loading_window():
    """Testa a janela de loading isoladamente."""
    import customtkinter

    # Configurar tema
    customtkinter.set_appearance_mode("system")
    customtkinter.set_default_color_theme("blue")

    # Criar janela de teste
    root = customtkinter.CTk()
    root.withdraw()  # Ocultar janela principal

    # Criar e testar loading
    loading = SimpleLoadingWindow()

    if loading.create_window():
        loading.show()

        # Simular progresso
        for i in range(11):
            progress = i / 10
            loading.update_status(f"Testando... {i*10}%", progress)
            time.sleep(0.3)

        loading.close()
        print("OK - Teste da janela de loading passou!")
        return True
    else:
        print("ERRO - Falha no teste da janela de loading")
        return False

if __name__ == "__main__":
    # Teste isolado
    test_loading_window()