# src/ferramentasderede/ui/components/context_menu.py
# Classe reutilizável para criar um menu de contexto para textboxes.

import tkinter as tk
from tkinter import filedialog
import logging

class TerminalContextMenu:
    def __init__(self, app, textbox):
        self.app = app
        self.textbox = textbox
        self.menu = tk.Menu(textbox, tearoff=0)
        
        self.menu.add_command(label="Copiar", command=self.copy_selection)
        self.menu.add_command(label="Copiar Tudo", command=self.copy_all)
        self.menu.add_separator()
        self.menu.add_command(label="Limpar Tela", command=self.clear_screen)
        self.menu.add_command(label="Exportar para Arquivo...", command=self.export_to_file)

        self.textbox.bind("<Button-3>", self.show_menu)
        self.textbox.bind("<Button-2>", self.show_menu)

    def show_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def copy_selection(self):
        logging.debug("Context menu: Copy Selection")
        try:
            selected_text = self.textbox.get("sel.first", "sel.last")
            if selected_text:
                self.app.clipboard_clear()
                self.app.clipboard_append(selected_text)
                self.app.show_toast_notification("Seleção copiada!")
        except tk.TclError:
            logging.warning("Context menu: No text selected for copying.")
        except Exception as e:
            logging.error(f"Context menu: Error copying selection: {e}")

    def copy_all(self):
        logging.debug("Context menu: Copy All")
        all_text = self.textbox.get("1.0", "end-1c")
        if all_text:
            self.app.clipboard_clear()
            self.app.clipboard_append(all_text)
            self.app.show_toast_notification("Todo o texto foi copiado!")

    def clear_screen(self):
        logging.debug("Context menu: Clear Screen")
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

    def export_to_file(self):
        all_text = self.textbox.get("1.0", "end-1c")
        if not all_text:
            logging.info("Context menu: No content to export.")
            self.app.show_info("Não há conteúdo para exportar.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Log files", "*.log"), ("All files", "*.*")],
            title="Salvar Saída Como"
        )

        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(all_text)
                self.app.show_toast_notification(f"Saída exportada para {filepath}")
                logging.info(f"Context menu: Output exported to {filepath}")
            except Exception as e:
                logging.error(f"Context menu: Error saving file: {e}")
                self.app.show_error(f"Erro ao salvar arquivo: {e}") # Keep showing error in UI