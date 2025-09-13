# app/translation_manager.py
# Gerencia o carregamento de traduções a partir de múltiplos arquivos JSON por idioma.

import json
import os
import glob
import logging

class TranslationManager:
    def __init__(self, languages_dir="languages", fallback_lang="pt-BR"):
        self.languages_dir = languages_dir
        self.fallback_lang = fallback_lang
        self.current_language_data = {}
        self.fallback_language_data = {}
        self._load_language_from_prefix(fallback_lang, is_fallback=True)

    def _load_language_from_prefix(self, lang_code, is_fallback=False):
        """Carrega e mescla todos os arquivos JSON de um idioma a partir de seu prefixo."""
        lang_files_pattern = os.path.join(self.languages_dir, f"{lang_code}-*.json")
        json_files = glob.glob(lang_files_pattern)
        translations = {}

        if not json_files:
            logging.warning(f"Nenhum arquivo de idioma com prefixo '{lang_code}-' foi encontrado em '{self.languages_dir}'.")
            if is_fallback:
                self.fallback_language_data = {}
            else:
                self.current_language_data = {}
            return

        for file_path in json_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    translations.update(data)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logging.warning(f"Não foi possível carregar o arquivo de tradução '{os.path.basename(file_path)}': {e}")

        if is_fallback:
            self.fallback_language_data = translations
        else:
            self.current_language_data = translations

    def set_language(self, lang_code):
        """Define o idioma atual a ser usado, carregando-o da pasta correspondente."""
        if lang_code != self.fallback_lang:
            self._load_language_from_prefix(lang_code)
        else:
            self.current_language_data = self.fallback_language_data

    def translate(self, text_key, **kwargs):
        """Traduz uma chave de texto, com fallback para o idioma padrão."""
        translated_text = self.current_language_data.get(text_key)
        
        if translated_text is None:
            translated_text = self.fallback_language_data.get(text_key, text_key)
            
        return translated_text.format(**kwargs)