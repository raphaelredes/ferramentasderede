# app/ui_components/service_manager/data_manager.py
# Lida com a lógica de dados para a lista de serviços: cache, filtro e paginação.

import os
import json
import math
from datetime import datetime

class ServiceDataManager:
    def __init__(self, cache_path):
        self.cache_path = cache_path
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        
        self.all_services = []
        self.current_view = []
        self.last_updated_timestamp = None

    def get_last_update_time(self):
        return self.last_updated_timestamp

    def load_from_cache(self):
        if not os.path.exists(self.cache_path):
            return False
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            self.set_data(cached_data.get('services', []))
            self.last_updated_timestamp = datetime.fromisoformat(cached_data.get('timestamp'))
            return True
        except (json.JSONDecodeError, FileNotFoundError, KeyError, TypeError):
            self.set_data([])
            self.last_updated_timestamp = None
            return False

    def save_to_cache(self):
        try:
            self.last_updated_timestamp = datetime.now()
            cache_content = {
                "timestamp": self.last_updated_timestamp.isoformat(),
                "services": self.all_services
            }
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_content, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar cache de serviços: {e}")

    def set_data(self, services_data):
        if isinstance(services_data, list) and services_data:
            self.all_services = sorted(services_data, key=lambda s: s.get("DisplayName", "").lower())
        else:
            self.all_services = services_data
        self.current_view = self.all_services

    def filter(self, term):
        term = term.lower()
        if not term:
            self.current_view = self.all_services
        elif isinstance(self.all_services, list):
            self.current_view = [
                s for s in self.all_services
                if isinstance(s, dict) and (
                    term in s.get("Name", "").lower() or term in s.get("DisplayName", "").lower()
                )
            ]
        else:
            self.current_view = []

    def get_page(self, page_number, items_per_page):
        if not isinstance(self.current_view, list):
            return [], 1, 1
            
        total_items = len(self.current_view)
        total_pages = max(1, math.ceil(total_items / items_per_page))
        current_page = max(1, min(page_number, total_pages))

        start_index = (current_page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_items = self.current_view[start_index:end_index]

        return page_items, current_page, total_pages

    def update_service_in_cache(self, service_name, new_data):
        if "error" in new_data or not isinstance(self.all_services, list):
            return

        found = False
        for i, service in enumerate(self.all_services):
            if isinstance(service, dict) and service.get("Name") == service_name:
                self.all_services[i] = new_data
                found = True
                break
        
        if found:
            self.save_to_cache()