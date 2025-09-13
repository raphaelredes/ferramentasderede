# src/ferramentasderede/ui/components/host_tab_manager/tab_manager.py
# Gerencia o widget CTkTabview, suas abas, status e eventos de hosts salvos.

import customtkinter
import logging
import tkinter
from PIL import Image, ImageDraw
from .home_tab_manager import HomeTabManager

class HostTabManager:
    def __init__(self, tab_view_widget, app, on_tab_change_callback):
        self.tab_view = tab_view_widget
        self.app = app
        self.on_tab_change_callback = on_tab_change_callback

        self.host_tabs_data = {}
        self.status_images = {}
        self.placeholder_name = "Home"
        self.right_clicked_tab_name = None

        self._create_context_menu()
        self.tab_view.configure(command=self._on_tab_selected)

    def _create_context_menu(self):
        self.context_menu = tkinter.Menu(self.tab_view, tearoff=0)

    def show_context_menu(self, event, clicked_button):
        """
        Mostra o menu de contexto. O botão clicado é passado diretamente como argumento.
        """
        clicked_tab_name = clicked_button.cget("text").strip()
        self.context_menu.delete(0, "end")
        
        if clicked_tab_name and clicked_tab_name != self.placeholder_name:
            self.right_clicked_tab_name = clicked_tab_name
            
            rename_text = self.app.translate("context_menu_set_nickname")
            self.context_menu.add_command(label=rename_text, command=self.rename_selected_host)
            change_ip_text = self.app.translate("context_menu_change_ip")
            self.context_menu.add_command(label=change_ip_text, command=self.change_ip_selected_host)
            
            self.context_menu.add_separator()
            
            delete_text = self.app.translate("context_menu_delete_host", display_name=self.right_clicked_tab_name)
            self.context_menu.add_command(label=delete_text, command=self.delete_selected_host)
            
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def get_host_from_clicked_tab(self):
        if not self.right_clicked_tab_name:
            return None
        return next((data['host_info'] for data in self.host_tabs_data.values() if self._get_display_name(data['host_info']) == self.right_clicked_tab_name), None)

    def delete_selected_host(self):
        host_to_remove = self.get_host_from_clicked_tab()
        if host_to_remove:
            self.app.controller.remove_single_host(host_to_remove)
        self.right_clicked_tab_name = None

    def rename_selected_host(self):
        host_to_rename = self.get_host_from_clicked_tab()
        if host_to_rename:
            self.app.controller.rename_host_nickname(host_to_rename)
        self.right_clicked_tab_name = None

    def change_ip_selected_host(self):
        host = self.get_host_from_clicked_tab()
        if host:
            try:
                from ..custom_input_dialog import CustomInputDialog
                dialog = CustomInputDialog(
                    app=self.app,
                    title=self.app.translate("context_menu_change_ip"),
                    text=self.app.translate("tab_settings_ip_label")
                )
                self.app.center_popup_on_main_window(dialog, 380, 180)
                new_ip = dialog.get_input()
                if new_ip:
                    self.app.controller.change_host_ip_manual(host, new_ip.strip())
            except Exception as e:
                import logging
                logging.error(f"Erro ao alterar IP manualmente: {e}")
        self.right_clicked_tab_name = None

    def _on_tab_selected(self, *args):
        selected_tab_name = self.tab_view.get()
        if selected_tab_name is None or selected_tab_name == self.placeholder_name:
            if self.app.host_tab_view.home_tab_manager:
                self.app.host_tab_view.home_tab_manager.update_home_buttons_state()
            return
        host_name_key = next((k for k, d in self.host_tabs_data.items() if self._get_display_name(d['host_info']) == selected_tab_name), None)
        if host_name_key:
            host_data = self.host_tabs_data.get(host_name_key)
            if host_data and self.on_tab_change_callback:
                self.on_tab_change_callback(host_data)

    def _get_display_name(self, host_info):
        base = host_info.get('nickname', '').strip() or host_info.get('name')
        try:
            ip = host_info.get('ip')
            if ip in ['127.0.0.1', '::1', 'localhost']:
                return f"{base} (localhost)"
        except Exception:
            pass
        return base

    def clear_all(self):
        for name in self.get_all_tab_names():
            try: self.tab_view.delete(name)
            except Exception: pass
        self.host_tabs_data.clear()

    def add_tab(self, host, switch_to=True):
        host_name_key = host['name']
        display_name = self._get_display_name(host)
        if display_name in self.tab_view._name_list: return
        self.tab_view.add(display_name)
        self.host_tabs_data[host_name_key] = {"host_info": host}
        self.app.after(50, lambda: self._store_button_reference_and_update_status(host_name_key, display_name))
        if switch_to: 
            # Aguardar um pouco para garantir que a aba foi criada
            self.app.after(100, lambda: self.tab_view.set(display_name))
            logging.debug(f"Aba '{display_name}' será selecionada automaticamente")

    def remove_tab(self, host):
        host_name_key = host['name']
        display_name = self._get_display_name(host)
        if display_name in self.tab_view._name_list: self.tab_view.delete(display_name)
        if host_name_key in self.host_tabs_data: del self.host_tabs_data[host_name_key]

    def populate_initial(self, hosts, select_tab_named: str = None):
        self.clear_all()
        for host in hosts:
            self.add_tab(host, switch_to=False)
        if select_tab_named and select_tab_named in self.tab_view._name_list:
            self.tab_view.set(select_tab_named)
        else:
            self.tab_view.set(self.placeholder_name)
    
    def _create_status_image(self, color, size=10):
        if color in self.status_images: return self.status_images[color]
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((0, 0, size - 1, size - 1), fill=color)
        ctk_image = customtkinter.CTkImage(light_image=image, dark_image=image, size=(size, size))
        self.status_images[color] = ctk_image
        return ctk_image

    def update_status_indicator(self, host_name_key):
        host_data = self.host_tabs_data.get(host_name_key)
        if not host_data or 'button_widget' not in host_data or not host_data['button_widget']: return
        button = host_data['button_widget']
        ip = host_data['host_info']['ip']
        status = self.app.host_statuses.get(ip, 'unknown')
        status_colors = {"online": "#2ECC71", "offline": "#E74C3C", "unknown": "#808080"}
        color_hex = status_colors.get(status, status_colors["unknown"])
        display_name = self._get_display_name(host_data['host_info'])
        status_image = self._create_status_image(color_hex)
        try:
            if button and button.winfo_exists():
                button.configure(image=status_image, compound="left", text=f" {display_name}")
        except Exception as e:
            print(f"Não foi possível atualizar o indicador de status para {display_name}: {e}")
            
    def _store_button_reference_and_update_status(self, host_name_key, display_name):
        if hasattr(self.tab_view, '_segmented_button') and self.tab_view._segmented_button.winfo_exists() and display_name in self.tab_view._segmented_button._buttons_dict:
            button = self.tab_view._segmented_button._buttons_dict[display_name]
            if host_name_key in self.host_tabs_data:
                self.host_tabs_data[host_name_key]['button_widget'] = button
                # CORREÇÃO DEFINITIVA: Usa lambda para passar o botão específico como argumento.
                button.bind("<Button-3>", lambda event, b=button: self.show_context_menu(event, b))
                self.update_status_indicator(host_name_key)
    
    def get_all_tab_names(self):
        return [name for name in self.tab_view._name_list if name != self.placeholder_name]
        
    def get_current_tab_name(self):
        """Retorna o nome da aba atualmente selecionada."""
        return self.tab_view.get()

    def update_language(self):
        for host_name_key in list(self.host_tabs_data.keys()):
            self.update_status_indicator(host_name_key)