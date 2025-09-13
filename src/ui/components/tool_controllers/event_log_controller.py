# app/ui_components/tool_controllers/event_log_controller.py

import threading
from .base_controller import BaseToolController, Q_ITEM_CALLBACK
from ..loading_window import LoadingWindow
import logging

class EventLogController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)
        self.event_log_frame = None

    def get_event_logs(self, log_name, level, count):
        """Inicia a busca de logs de eventos de forma independente."""
        if self.is_running:
            self.app.show_info(f"Um comando ({self.running_command}) já está em execução.")
            return

        username, password = self._get_credentials_with_vault()
        if not username:
            self.app.show_info(self.app.translate("user_cancelled_operation"))
            return

        loading_text = self.app.translate("event_log_loading", count=count, level=level, log_name=log_name)
        loading_window = LoadingWindow(self.app, loading_text)

        self.is_running = True
        self.running_command = "get_logs"
        self._notify_state_change()

        def thread_wrapper():
            try:
                self._get_event_logs_worker(username, password, log_name, level, count)
            except Exception as e:
                logging.error(f"Erro não tratado na thread 'get_logs': {e}")
                if self._is_winrm_connection_error(e):
                    self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
            finally:
                # Garante que a destruição da janela de loading seja agendada na thread principal
                if loading_window and hasattr(loading_window, '_destroyed') and not loading_window._destroyed:
                    def safe_destroy():
                        try:
                            if hasattr(loading_window, '_destroyed') and not loading_window._destroyed and loading_window.winfo_exists():
                                loading_window.destroy()
                                logging.debug(f"LoadingWindow destroyed successfully")
                        except Exception as e:
                            logging.debug(f"Error in safe_destroy: {e}")
                            # Última tentativa: marcar como destruída
                            try:
                                loading_window._destroyed = True
                            except:
                                pass
                    
                    # Múltiplas tentativas de destruição
                    try:
                        # Primeira tentativa: after_idle
                        self.app.after_idle(safe_destroy)
                    except Exception as e:
                        logging.debug(f"Error scheduling after_idle destroy: {e}")
                        try:
                            # Segunda tentativa: after com delay
                            self.app.after(50, safe_destroy)
                        except Exception as e2:
                            logging.debug(f"Error scheduling after destroy: {e2}")
                            try:
                                # Terceira tentativa: after com delay maior
                                self.app.after(200, safe_destroy)
                            except Exception as e3:
                                logging.debug(f"Error in third attempt to destroy loading window: {e3}")
                                # Última tentativa: marcar como destruída
                                try:
                                    loading_window._destroyed = True
                                except:
                                    pass
                # Usa um callback para chamar _command_finished para garantir a execução na thread principal
                self._put_in_queue(Q_ITEM_CALLBACK, (self._command_finished, (False,), {}))
                
        threading.Thread(target=thread_wrapper, daemon=True).start()
        self.process_queue()

    def _get_event_logs_worker(self, username, password, log_name, level, count):
        """Worker que executa o comando remoto e envia os dados para a UI."""
        logging.debug(f"Starting event logs worker for {log_name}, level {level}, count {count}")
        
        event_data = self.system_tools.get_remote_event_logs(self.host['ip'], username, password, log_name, level, count)
        
        logging.debug(f"Event data received: type={type(event_data)}, length={len(event_data) if event_data else 0}")
        if event_data:
            logging.debug(f"First event data item: {event_data[0] if isinstance(event_data, list) and len(event_data) > 0 else event_data}")
            if isinstance(event_data, list) and len(event_data) > 0:
                for i, item in enumerate(event_data):
                    logging.debug(f"Item {i}: type={type(item)}, value={item}")
                    if isinstance(item, dict):
                        logging.debug(f"  Item {i} keys: {list(item.keys())}")
                        if "error" in item:
                            logging.debug(f"  Item {i} is an error: {item['error']}")
                    elif isinstance(item, str):
                        logging.debug(f"  Item {i} string length: {len(item)}")
                        logging.debug(f"  Item {i} string content: {item[:200]}...")  # Primeiros 200 caracteres
        
        # Verificar se há erros nos dados
        if isinstance(event_data, list) and len(event_data) > 0:
            first_item = event_data[0]
            if isinstance(first_item, dict) and "error" in first_item:
                error_info = first_item
                logging.warning(f"Error in event data: {error_info}")
                error_message = error_info.get("error", "Erro desconhecido")
                if self._is_winrm_connection_error(error_info.get("exception_type")):
                    self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
                else:
                    self._put_in_queue(Q_ITEM_CALLBACK, (self.event_log_frame.display_error, (error_message,), {}))
                return

        if not event_data:
            logging.info(f"No event data received for {log_name}, level {level}")
            no_events_message = self.app.translate("event_logs_none_found", level=level, log_name=log_name)
            self._put_in_queue(Q_ITEM_CALLBACK, (self.event_log_frame.display_error, (no_events_message,), {}))
            return

        logging.info(f"Sending {len(event_data)} event logs to UI")
        self._put_in_queue(Q_ITEM_CALLBACK, (self.event_log_frame.update_log_display, (event_data,), {}))
