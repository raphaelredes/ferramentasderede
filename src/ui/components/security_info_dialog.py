# src/ferramentasderede/ui/components/security_info_dialog.py
# Janela de ajuda detalhada sobre o funcionamento do cofre de credenciais.

import customtkinter
from .base_dialog import BaseDialog

class SecurityInfoDialog(BaseDialog):
    def __init__(self, app):
        super().__init__(app=app, title=app.translate("security_main_title"))
        
        # Definir tamanho mínimo adequado para o conteúdo
        self.minsize(600, 480)
        
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        tab_view = customtkinter.CTkTabview(main_frame, anchor="w")
        tab_view.grid(row=0, column=0, sticky="nsew")

        self._create_how_it_works_tab(tab_view.add(self.app.translate("security_tab_how_it_works")))
        self._create_session_security_tab(tab_view.add(self.app.translate("security_tab_session")))
        self._create_security_tips_tab(tab_view.add(self.app.translate("security_tab_tips")))

        close_button = customtkinter.CTkButton(self, text=self.app.translate("label_close"), command=self.destroy)
        close_button.grid(row=1, column=0, pady=(10, 10))
        
        self.bind("<Escape>", lambda e: self.destroy())

    def _create_info_label(self, master, text_key, bold=False, indent=0, space_after=0):
        font = customtkinter.CTkFont(size=13, weight="bold" if bold else "normal")
        text = self.app.translate(text_key)
        label = customtkinter.CTkLabel(master, text=text, font=font, justify="left", anchor="w", wraplength=520)
        label.pack(fill="x", padx=(10 + indent, 10), pady=(5, space_after))
        return label

    def _create_how_it_works_tab(self, tab):
        scroll_frame = customtkinter.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        self._create_info_label(scroll_frame, "security_master_pass_title", bold=True, space_after=5)
        self._create_info_label(scroll_frame, "security_master_pass_desc", indent=15, space_after=10)

        self._create_info_label(scroll_frame, "security_key_derivation_title", bold=True, space_after=5)
        self._create_info_label(scroll_frame, "security_key_derivation_desc", indent=15, space_after=10)
            
        self._create_info_label(scroll_frame, "security_encryption_title", bold=True, space_after=5)
        self._create_info_label(scroll_frame, "security_encryption_desc", indent=15)

    def _create_session_security_tab(self, tab):
        scroll_frame = customtkinter.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)
        
        self._create_info_label(scroll_frame, "security_session_title", bold=True, space_after=10)
        
        self._create_info_label(scroll_frame, "security_session_temp_files_title", bold=True, indent=15)
        self._create_info_label(scroll_frame, "security_session_temp_files_desc", indent=30, space_after=10)
            
        self._create_info_label(scroll_frame, "security_session_auto_delete_title", bold=True, indent=15)
        self._create_info_label(scroll_frame, "security_session_auto_delete_desc", indent=30)
            
    def _create_security_tips_tab(self, tab):
        scroll_frame = customtkinter.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        self._create_info_label(scroll_frame, "security_tips_intro", bold=True, space_after=10)
        
        self._create_info_label(scroll_frame, "security_tips_strong_pass_title", bold=True, indent=15)
        self._create_info_label(scroll_frame, "security_tips_strong_pass_desc", indent=30, space_after=10)

        self._create_info_label(scroll_frame, "security_tips_pc_security_title", bold=True, indent=15)
        self._create_info_label(scroll_frame, "security_tips_pc_security_desc", indent=30, space_after=10)
            
        self._create_info_label(scroll_frame, "security_tips_no_sharing_title", bold=True, indent=15)
        self._create_info_label(scroll_frame, "security_tips_no_sharing_desc", indent=30)