# app/ui_components/welcome_dialog.py

import os
import customtkinter
from PIL import Image
import logging
from .base_dialog import BaseDialog # Herda da BaseDialog unificada

class WelcomeDialog(BaseDialog):
    def __init__(self, app):
        super().__init__(app, title=app.translate("welcome_title"))
        logging.info("WelcomeDialog is being shown.")

        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=25, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        try:
            light_icon_path = os.path.join(self.app.base_dir, "assets", "icon_light.png")
            dark_icon_path = os.path.join(self.app.base_dir, "assets", "icon_dark.png")
            
            if os.path.exists(light_icon_path) and os.path.exists(dark_icon_path):
                logo_image = customtkinter.CTkImage(
                    light_image=Image.open(light_icon_path), 
                    dark_image=Image.open(dark_icon_path), 
                    size=(96, 96)
                )
                logo_label = customtkinter.CTkLabel(main_frame, image=logo_image, text="")
                logo_label.grid(row=0, column=0, pady=(10, 15))
        except Exception as e:
            print(f"Aviso: Não foi possível carregar a logo para a tela de boas-vindas: {e}")

        intro_label = customtkinter.CTkLabel(
            main_frame,
            text=self.app.translate("welcome_intro"),
            font=customtkinter.CTkFont(size=14),
            text_color=("gray20", "gray80")
        )
        intro_label.grid(row=2, column=0, pady=(0, 20))

        features_list_label = customtkinter.CTkLabel(
            main_frame,
            text=self.app.translate("about_features_list"),
            wraplength=480,
            justify="left"
        )
        features_list_label.grid(row=3, column=0, pady=(0, 25), padx=10)

        ok_button = customtkinter.CTkButton(
            main_frame,
            text=self.app.translate("label_ok"),
            command=self.destroy
        )
        ok_button.grid(row=4, column=0, pady=(0, 10), padx=40, sticky="ew")
        
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())